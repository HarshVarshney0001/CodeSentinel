import os
import base64
import requests
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "HarshVarshney0001"
REPO_NAME = "codesentinel-test-repo"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

mcp = MCPServer("CodeSentinel")


@mcp.tool()
def fetch_pr_diff(pr_number: int) -> str:
    """Fetch the diff (changed lines only) of all files changed in a given GitHub Pull Request."""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/pulls/{pr_number}/files"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"Error fetching PR files: {response.status_code}"

    files = response.json()
    result = ""
    for f in files:
        result += f"\nFile: {f['filename']} ({f['status']})\n"
        result += f.get('patch', 'No diff available') + "\n"
    return result


@mcp.tool()
def fetch_full_file(filepath: str, branch: str) -> str:
    """Fetch the full current content of a specific file from a specific branch of the repo."""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{filepath}?ref={branch}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"Error fetching file: {response.status_code}"

    data = response.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return content


@mcp.tool()
def post_pr_comment(pr_number: int, comment_body: str) -> str:
    """Post a code review comment on a GitHub Pull Request."""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/issues/{pr_number}/comments"
    payload = {"body": comment_body}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return f"Comment posted successfully: {response.json()['html_url']}"
    else:
        return f"Failed to post comment: {response.status_code}"


@mcp.tool()
def search_related_code(query: str, n_results: int = 3) -> str:
    """
    Search the entire codebase for functions related to a given description or piece of code.
    Use this to check if a changed function is used elsewhere in the codebase, or to find
    similar/related code that might be affected by a change.
    """
    from rag_store import search_related_code as _search

    results = _search(query, n_results=n_results)

    if not results['ids'][0]:
        return "No related code found."

    output = ""
    for i in range(len(results['ids'][0])):
        meta = results['metadatas'][0][i]
        distance = results['distances'][0][i]
        output += (
            f"\nMatch {i+1}: {meta['filename']} :: {meta['function_name']}() "
            f"(lines {meta['start_line']}-{meta['end_line']}, similarity distance: {distance:.4f})\n"
        )
    return output


if __name__ == "__main__":
    mcp.run(transport="stdio")