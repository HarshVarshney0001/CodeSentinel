import asyncio
import json
import os
import sys
from dotenv import load_dotenv
from groq import Groq, BadRequestError
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

server_params = StdioServerParameters(
    command=sys.executable,
    args=["mcp_server.py"],
)


def mcp_tool_to_groq_format(tool):
    """MCP tool ko Groq/OpenAI ke function-calling format mein convert karo"""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        }
    }


def call_llm_with_retry(messages, tools, max_retries=3):
    """
    Groq LLM ko call karo. Kabhi-kabhi model ek malformed JSON tool-call
    generate kar deta hai (Groq isko 'tool_use_failed' error deta hai).
    Ye function aise failure par automatically dobara try karta hai,
    taaki poora agent crash na ho.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2
            )
            return response
        except BadRequestError as e:
            last_error = e
            print(f"⚠️ Tool call generation failed (attempt {attempt}/{max_retries}). Retrying...")
            continue

    raise last_error


async def run_agent(pr_number: int, branch: str):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            groq_tools = [mcp_tool_to_groq_format(t) for t in tools_result.tools]

            print(f"🔧 Agent ko available tools mile: {[t.name for t in tools_result.tools]}\n")

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are CodeSentinel, an AI code review agent for GitHub Pull Requests. "
                        "You have tools to fetch a PR's diff, fetch a file's full content, search the "
                        "codebase for related code, and post a review comment.\n"
                        "Your job: review the given Pull Request thoroughly.\n"
                        "Process:\n"
                        "1) Fetch the diff for the PR ONCE.\n"
                        "2) For each changed file, fetch its full content from the PR's branch EXACTLY ONCE.\n"
                        "3) For the function(s) that were changed in the diff, use the search-related-code tool "
                        "ONCE per changed function to check if that function is used or referenced elsewhere "
                        "in the codebase. Use a short natural language description of the function as the query "
                        "(e.g. 'function that divides two numbers'), not the raw code.\n"
                        "4) Write a review with THREE sections:\n"
                        "   - 'Changed Lines Review': comment only on the lines shown in the diff.\n"
                        "   - 'Pre-existing Issues Found': bugs elsewhere in the file (ignore indentation/formatting).\n"
                        "   - 'Cross-Codebase Impact': based on the search-related-code results, mention if the "
                        "changed function is used elsewhere and whether that usage could be affected by any "
                        "issues found. If no related usage was found or nothing is affected, say 'No cross-file "
                        "impact found.'\n"
                        "5) Post the final review as a single comment using the post comment tool.\n"
                        "IMPORTANT RULES:\n"
                        "- Never call the same tool with the same arguments more than once.\n"
                        "- Do not re-fetch information you already have.\n"
                        "- Format the comment_body using clear markdown: use '##' for section headers and '**bold**' "
                        "for function names, exactly as in a normal GitHub comment.\n"
                        "- Do NOT wrap function or variable names in backticks (`) or double quotes inside comment_body, "
                        "since this can break JSON formatting. Use bold (**text**) instead of backticks for code terms.\n"
                        "- Always finish the task by actually calling the comment-posting tool."
                    )
                },
                {
                    "role": "user",
                    "content": f"Review PR #{pr_number} on branch '{branch}'."
                }
            ]

            max_turns = 10
            for turn in range(max_turns):
                response = call_llm_with_retry(messages, groq_tools)

                msg = response.choices[0].message

                assistant_entry = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    assistant_entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in msg.tool_calls
                    ]
                messages.append(assistant_entry)

                if not msg.tool_calls:
                    print("\n=== ✅ Agent has finished its work ===")
                    print(msg.content)
                    break

                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    print(f"🔧 Agent decided to call: {tool_name}({tool_args})")

                    result = await session.call_tool(tool_name, tool_args)
                    result_text = result.content[0].text if result.content else ""

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text
                    })


if __name__ == "__main__":
    PR_NUMBER = 2
    BRANCH_NAME = "HarshVarshney0001-patch-1"
    asyncio.run(run_agent(PR_NUMBER, BRANCH_NAME))