from typing import TypedDict, Optional
import requests
import os
import base64
from dotenv import load_dotenv
from groq import Groq
from rag_store import search_related_code
from langgraph.graph import StateGraph, END

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "HarshVarshney0001"
REPO_NAME = "codesentinel-test-repo"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


class ReviewState(TypedDict):
    """
    Ye poore graph ka 'shared memory' hai. Har node isko padhega,
    apna kaam karega, aur update karke agle node ko dega.
    """
    pr_number: int
    branch: str

    diff: Optional[str]
    changed_files: Optional[list]

    diff_review: Optional[str]

    related_code_context: Optional[str]

    pre_existing_issues: Optional[str]

    should_comment: Optional[bool]
    final_review: Optional[str]

    comment_posted: Optional[bool]
    comment_url: Optional[str]


def fetch_diff_node(state: ReviewState) -> ReviewState:
    """
    NODE 1: GitHub se PR ka diff fetch karta hai.
    State ka 'pr_number' padhta hai, 'diff' aur 'changed_files' fill karta hai.
    """
    pr_number = state["pr_number"]
    print(f"🔵 [Node: fetch_diff] PR #{pr_number} ka diff fetch kar raha hoon...")

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/pulls/{pr_number}/files"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Error fetching diff: {response.status_code}")
        state["diff"] = ""
        state["changed_files"] = []
        return state

    files = response.json()

    diff_text = ""
    filenames = []
    for f in files:
        diff_text += f"\nFile: {f['filename']} ({f['status']})\n"
        diff_text += f.get('patch', 'No diff available') + "\n"
        filenames.append(f['filename'])

    state["diff"] = diff_text
    state["changed_files"] = filenames

    print(f"✅ [Node: fetch_diff] Diff mil gaya. Changed files: {filenames}")
    return state


def code_quality_check_node(state: ReviewState) -> ReviewState:
    """
    NODE 2: Sirf diff (changed lines) ko review karta hai LLM se.
    State ka 'diff' padhta hai, 'diff_review' fill karta hai.
    """
    print(f"🔵 [Node: code_quality_check] Diff ka review kar raha hoon...")

    prompt = f"""You are an expert code reviewer. Review ONLY the following diff
(the exact lines changed in a Pull Request). Do not comment on anything outside these lines.

DIFF:
{state['diff']}

State clearly whether each change is correct, or if it introduces a bug.
Do NOT report indentation or formatting issues. Be concise (3-4 sentences max).
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    review_text = response.choices[0].message.content
    state["diff_review"] = review_text

    print(f"✅ [Node: code_quality_check] Diff review complete.")
    return state


def rag_context_node(state: ReviewState) -> ReviewState:
    """
    NODE 3: Changed files ke functions ke liye related code dhundta hai
    ChromaDB se (RAG). State ka 'changed_files' padhta hai,
    'related_code_context' fill karta hai.
    """
    print(f"🔵 [Node: rag_context] Related code dhoond raha hoon...")

    changed_files = state["changed_files"]
    context_parts = []

    for filename in changed_files:
        query = f"functions changed in {filename}"
        results = search_related_code(query, n_results=3)

        if results['ids'][0]:
            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                context_parts.append(
                    f"- {meta['filename']} :: {meta['function_name']}() "
                    f"(similarity distance: {distance:.4f})"
                )

    context_text = "\n".join(context_parts) if context_parts else "No related code found."
    state["related_code_context"] = context_text

    print(f"✅ [Node: rag_context] Related code mil gaya.")
    return state


def fetch_full_file(filepath, branch):
    """Helper function - ek file ka poora content fetch karta hai"""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{filepath}?ref={branch}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    data = response.json()
    return base64.b64decode(data['content']).decode('utf-8')


def bug_detection_node(state: ReviewState) -> ReviewState:
    """
    NODE 4: Poori file(s) fetch karke pre-existing bugs dhundta hai
    (jo diff se related nahi hain). State ka 'changed_files' aur 'branch'
    padhta hai, 'pre_existing_issues' fill karta hai.
    """
    print(f"🔵 [Node: bug_detection] Poori file scan kar raha hoon...")

    changed_files = state["changed_files"]
    branch = state["branch"]
    all_issues = []

    for filename in changed_files:
        full_content = fetch_full_file(filename, branch)
        if full_content is None:
            continue

        prompt = f"""You are an expert code reviewer. Review the ENTIRE content of this file
(not just recent changes). Find any bugs, missing validations, or edge cases that already
existed in the code (ignore indentation/formatting issues).

FILE: {filename}
CONTENT:
{full_content}

List each issue with the function name and a short explanation. If none, say "No issues found."
Be concise.
"""

        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        issues_text = response.choices[0].message.content
        all_issues.append(f"File: {filename}\n{issues_text}")

    state["pre_existing_issues"] = "\n\n".join(all_issues)

    print(f"✅ [Node: bug_detection] Bug detection complete.")
    return state


def decide_node(state: ReviewState) -> ReviewState:
    """
    NODE 5: Decide karta hai ki comment post karna chahiye ya nahi,
    aur final review text banata hai. State ke saare pichhle fields
    padhta hai, 'should_comment' aur 'final_review' fill karta hai.
    """
    print(f"🔵 [Node: decide] Decide kar raha hoon comment karna hai ya nahi...")

    prompt = f"""You are CodeSentinel, an AI code review agent. Based on the following
analysis of a Pull Request, decide if a review comment is worth posting, and write it.

DIFF REVIEW:
{state['diff_review']}

RELATED CODE (for cross-file context):
{state['related_code_context']}

PRE-EXISTING ISSUES FOUND IN THE FILE:
{state['pre_existing_issues']}

Instructions:
1. If there are NO real bugs or meaningful issues anywhere above (diff review is clean AND
   pre-existing issues say "No issues found"), respond with exactly: SKIP_COMMENT
2. Otherwise, write a review comment in markdown with these sections:
   ## Changed Lines Review
   ## Pre-existing Issues Found
   ## Cross-Codebase Impact
   Use '##' for headers and '**bold**' for function names. Avoid backticks and double
   quotes inside the text where possible.
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    result_text = response.choices[0].message.content.strip()

    if result_text == "SKIP_COMMENT":
        state["should_comment"] = False
        state["final_review"] = None
        print(f"⚪ [Node: decide] Decision: SKIP — koi genuine issue nahi mila.")
    else:
        state["should_comment"] = True
        state["final_review"] = result_text
        print(f"✅ [Node: decide] Decision: COMMENT — issues mile hain.")

    return state


def post_comment_node(state: ReviewState) -> ReviewState:
    """
    NODE 6: Agar should_comment True hai, review ko GitHub PR par
    comment ki tarah post karta hai. Warna skip kar deta hai.
    """
    if not state["should_comment"]:
        print(f"⚪ [Node: post_comment] Comment skip kiya gaya (koi genuine issue nahi tha).")
        state["comment_posted"] = False
        state["comment_url"] = None
        return state

    print(f"🔵 [Node: post_comment] Comment post kar raha hoon...")

    pr_number = state["pr_number"]
    comment_body = state["final_review"]

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/issues/{pr_number}/comments"
    payload = {"body": comment_body}
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        state["comment_posted"] = True
        state["comment_url"] = response.json()['html_url']
        print(f"✅ [Node: post_comment] Comment posted: {state['comment_url']}")
    else:
        state["comment_posted"] = False
        state["comment_url"] = None
        print(f"❌ [Node: post_comment] Failed to post comment: {response.status_code}")

    return state


def build_graph():
    """LangGraph StateGraph banata hai, saare 6 nodes ko connect karke"""
    graph = StateGraph(ReviewState)

    graph.add_node("fetch_diff", fetch_diff_node)
    graph.add_node("code_quality_check", code_quality_check_node)
    graph.add_node("rag_context", rag_context_node)
    graph.add_node("bug_detection", bug_detection_node)
    graph.add_node("decide", decide_node)
    graph.add_node("post_comment", post_comment_node)

    graph.set_entry_point("fetch_diff")

    graph.add_edge("fetch_diff", "code_quality_check")
    graph.add_edge("code_quality_check", "rag_context")
    graph.add_edge("rag_context", "bug_detection")
    graph.add_edge("bug_detection", "decide")
    graph.add_edge("decide", "post_comment")
    graph.add_edge("post_comment", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()

    initial_state: ReviewState = {
        "pr_number": 2,
        "branch": "HarshVarshney0001-patch-1",
        "diff": None,
        "changed_files": None,
        "diff_review": None,
        "related_code_context": None,
        "pre_existing_issues": None,
        "should_comment": None,
        "final_review": None,
        "comment_posted": None,
        "comment_url": None,
    }

    print("Running the LangGraph pipeline...\n")
    final_state = app.invoke(initial_state)

    print("\n" + "=" * 70)
    print("FINAL RESULT (via LangGraph):")
    print("=" * 70)
    print(f"should_comment: {final_state['should_comment']}")
    print(f"comment_posted: {final_state['comment_posted']}")
    print(f"comment_url: {final_state['comment_url']}")