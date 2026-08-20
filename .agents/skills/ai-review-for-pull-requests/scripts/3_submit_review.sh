#!/bin/bash
# Submits the AI-generated review to GitHub

ACP_REPO_DIR=$1
PR_NUMBER=$2
REVIEW_BODY_FILE=$3

if [ -z "$ACP_REPO_DIR" ] || [ -z "$PR_NUMBER" ] || [ -z "$REVIEW_BODY_FILE" ]; then
    echo "Error: Missing arguments."
    echo "Usage: ./3_submit_review.sh <ACP_REPO_DIR> <PR_NUMBER> <path_to_markdown_review_body.md>"
    exit 1
fi

if [ ! -f "$REVIEW_BODY_FILE" ]; then
    echo "Error: Review body file '$REVIEW_BODY_FILE' not found."
    exit 1
fi

cd "$ACP_REPO_DIR" || { echo "Error: Cannot navigate to $ACP_REPO_DIR"; exit 1; }

echo "--- Submitting PR Review ---"
gh pr review "$PR_NUMBER" --body-file "$REVIEW_BODY_FILE" --comment

echo "✓ AI Review successfully posted to PR #$PR_NUMBER."
