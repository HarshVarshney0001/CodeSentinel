import os
import ast
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "HarshVarshney0001"
REPO_NAME = "codesentinel-test-repo"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}


def list_repo_python_files(branch="main"):
    """Repo ke root folder ke saare .py files ki list nikalo"""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/?ref={branch}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error listing files: {response.status_code}")
        return []

    files = response.json()
    py_files = [f['name'] for f in files if f['name'].endswith('.py')]
    return py_files


def fetch_file_content(filepath, branch="main"):
    """Ek file ka poora content fetch karo"""
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{filepath}?ref={branch}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching {filepath}: {response.status_code}")
        return None
    data = response.json()
    return base64.b64decode(data['content']).decode('utf-8')


def chunk_file_by_function(filename, file_content):
    """
    File ko function-level chunks mein todo, using AST. Agar file mein
    syntax error ho (parse na ho paye), poori file ko ek fallback
    chunk ki tarah rakho — taaki data loss na ho.
    """
    chunks = []
    try:
        tree = ast.parse(file_content)
    except SyntaxError as e:
        print(f"⚠️ Could not parse {filename} with AST (syntax error: {e}). "
              f"Using whole-file fallback chunk instead.")
        chunks.append({
            "filename": filename,
            "function_name": "(whole file - syntax error present)",
            "start_line": 1,
            "end_line": len(file_content.splitlines()),
            "code": file_content
        })
        return chunks

    lines = file_content.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = node.lineno - 1
            end_line = node.end_lineno
            func_code = "\n".join(lines[start_line:end_line])

            chunks.append({
                "filename": filename,
                "function_name": node.name,
                "start_line": node.lineno,
                "end_line": node.end_lineno,
                "code": func_code
            })

    return chunks


def build_repo_chunks(branch="main"):
    """Poore repo ke saare functions ka chunk list banao"""
    all_chunks = []
    py_files = list_repo_python_files(branch)
    print(f"Found {len(py_files)} Python files: {py_files}\n")

    for filename in py_files:
        content = fetch_file_content(filename, branch)
        if content is None:
            continue
        file_chunks = chunk_file_by_function(filename, content)
        all_chunks.extend(file_chunks)

    return all_chunks


if __name__ == "__main__":
    chunks = build_repo_chunks(branch="main")

    print(f"Total chunks created: {len(chunks)}\n")
    print("=" * 70)

    for chunk in chunks:
        print(f"📄 {chunk['filename']} :: {chunk['function_name']}() "
              f"(lines {chunk['start_line']}-{chunk['end_line']})")
        print("-" * 70)
        print(chunk['code'])
        print("=" * 70)