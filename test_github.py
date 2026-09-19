import os
from dotenv import load_dotenv
import requests
import base64

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "HarshVarshney0001"
REPO_NAME = "codesentinel-test-repo"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def get_pr_files(pr_number):
    """PR mein kaunsi files change hui, aur unka diff nikalo"""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/pulls/{pr_number}/files"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Failed to fetch PR files. Status: {response.status_code}")
        print(response.json())
        return []

    return response.json()

def get_full_file_content(filepath, branch):
    """Us file ka POORA content nikalo (specific branch se)"""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{filepath}?ref={branch}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Failed to fetch full file. Status: {response.status_code}")
        return None

    data = response.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return content

def structure_pr_data(pr_number, branch_name):
    """Diff + Full file dono ko structured format mein lao"""
    files = get_pr_files(pr_number)

    structured_data = []

    for file in files:
        filename = file['filename']
        diff = file.get('patch', 'No diff available (binary or new file)')
        status = file['status']  # added, modified, removed

        full_content = get_full_file_content(filename, branch_name)

        file_info = {
            "filename": filename,
            "status": status,
            "diff": diff,
            "full_content": full_content
        }
        structured_data.append(file_info)

    return structured_data

if __name__ == "__main__":
    PR_NUMBER = 2
    BRANCH_NAME = "HarshVarshney0001-patch-1"

    print(f"Fetching data for PR #{PR_NUMBER}...\n")
    data = structure_pr_data(PR_NUMBER, BRANCH_NAME)

    for file in data:
        print("=" * 60)
        print(f"📄 File: {file['filename']} ({file['status']})")
        print("=" * 60)
        print("\n--- DIFF (changed lines only) ---")
        print(file['diff'])
        print("\n--- FULL FILE CONTENT ---")
        print(file['full_content'])
        print("\n")