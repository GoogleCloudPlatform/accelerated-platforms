#!/bin/bash
# Fetches the PR diff and the architecture guidelines

ACP_REPO_DIR=$1
PR_NUMBER=$2

if [ -z "$ACP_REPO_DIR" ] || [ -z "$PR_NUMBER" ]; then
    echo "Error: Missing arguments. Usage: ./2_fetch_context.sh <ACP_REPO_DIR> <PR_NUMBER>"
    exit 1
fi

cd "$ACP_REPO_DIR" || { echo "Error: Cannot navigate to $ACP_REPO_DIR"; exit 1; }

echo "--- 1. Architecture Document (gemini.md) ---"
if [ -f "gemini.md" ]; then
    cat gemini.md
else
    echo "Warning: gemini.md not found in the repository root. Architecture validation will be skipped."
fi

echo -e "\n--- 2. Pull Request Diff ---"
gh pr diff "$PR_NUMBER" || { echo "Error: Failed to fetch PR diff. Ensure you are authenticated with 'gh auth login'."; exit 1; }
