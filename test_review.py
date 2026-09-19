import os
import textwrap
import requests
from dotenv import load_dotenv
from groq import Groq
from test_github import structure_pr_data

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "HarshVarshney0001"
REPO_NAME = "codesentinel-test-repo"

client = Groq(api_key=GROQ_API_KEY)

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}


def build_prompt(file_info):
    prompt = f"""You are an expert code reviewer. Review the following Python file that was modified in a Pull Request.

FILE NAME: {file_info['filename']}

Here is the DIFF (the exact lines that were changed in this PR):
{file_info['diff']}

Here is the FULL CURRENT CONTENT of the file (including the changes above):
```python
{file_info['full_content']}
```

Please provide your review in exactly this format:

## Changed Lines Review
(Comment only on the lines shown in the DIFF above. State clearly if the change is correct, or if it introduces a bug.)

## Pre-existing Issues Found
(Now review the ENTIRE file content, including lines NOT part of the diff. List any bugs, missing validations, edge cases, or issues that already existed in the code before this PR. For each issue, mention the approximate line/function name and a short explanation. Do NOT report indentation or formatting issues — assume the code shown is correctly formatted; focus only on logic bugs.)

Be specific and concise. If there are no issues in a section, say "No issues found."
"""
    return textwrap.dedent(prompt)


def get_llm_review(prompt):
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content


def post_comment_to_pr(pr_number, comment_body):
    """Review ko GitHub PR par comment ki tarah post karo"""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/issues/{pr_number}/comments"
    payload = {"body": comment_body}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        print(f"✅ Comment successfully posted on PR #{pr_number}!")
        print(f"View it here: {response.json()['html_url']}")
    else:
        print(f"❌ Failed to post comment. Status: {response.status_code}")
        print(response.json())


if __name__ == "__main__":
    PR_NUMBER = 2
    BRANCH_NAME = "HarshVarshney0001-patch-1"

    print(f"Fetching PR #{PR_NUMBER} data...\n")
    files_data = structure_pr_data(PR_NUMBER, BRANCH_NAME)

    for file_info in files_data:
        print("=" * 70)
        print(f"🔍 Reviewing: {file_info['filename']}")
        print("=" * 70)

        prompt = build_prompt(file_info)
        review = get_llm_review(prompt)

        print(review)
        print("\n")

        # Comment ko achhe format mein banao
        comment_body = f"## 🔍 CodeSentinel Review — `{file_info['filename']}`\n\n{review}"

        # GitHub PR par post karo
        post_comment_to_pr(PR_NUMBER, comment_body)