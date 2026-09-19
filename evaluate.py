import os
import requests
import base64
from dotenv import load_dotenv
from groq import Groq
from ground_truth import GROUND_TRUTH_BUGS

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "HarshVarshney0001"
REPO_NAME = "codesentinel-test-repo"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def fetch_full_file(filepath, branch="main"):
    """Ek file ka poora content fetch karta hai"""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{filepath}?ref={branch}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    data = response.json()
    return base64.b64decode(data['content']).decode('utf-8')


def detect_bugs_in_file(filename, content):
    """LLM se ek file ke bugs detect karwata hai"""
    prompt = f"""You are an expert code reviewer. Review the ENTIRE content of this file.
Find any bugs, missing validations, or edge cases (ignore indentation/formatting issues).

FILE: {filename}
CONTENT:
{content}

List each issue found, one per line, in this exact format:
FUNCTION_NAME: short description of the bug

If a function has no issues, do not list it. Be thorough but concise.
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return response.choices[0].message.content


def run_evaluation():
    """Saari files ke ground-truth files par agent chalata hai, result collect karta hai"""
    files_to_check = list(set(bug["file"] for bug in GROUND_TRUTH_BUGS))

    all_results = {}

    for filename in files_to_check:
        print(f"🔵 Analyzing {filename}...")
        content = fetch_full_file(filename)
        if content is None:
            print(f"❌ Could not fetch {filename}")
            continue

        result = detect_bugs_in_file(filename, content)
        all_results[filename] = result
        print(f"✅ Done with {filename}\n")

    return all_results


if __name__ == "__main__":
    results = run_evaluation()

    print("\n" + "=" * 70)
    print("AGENT'S FULL OUTPUT (for manual comparison with ground truth):")
    print("=" * 70)

    for filename, result in results.items():
        print(f"\n--- {filename} ---")
        print(result)

    # Result ko file mein bhi save karo, taaki baad mein use kar sakein
    with open("agent_output.txt", "w", encoding="utf-8") as f:
        for filename, result in results.items():
            f.write(f"\n--- {filename} ---\n")
            f.write(result)
            f.write("\n")

    print("\n✅ Results saved to agent_output.txt")