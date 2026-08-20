#!/bin/bash
# Fetches CI/CD workflow status and failed logs for the PR

ACP_REPO_DIR=$1
PR_NUMBER=$2

if [ -z "$ACP_REPO_DIR" ] || [ -z "$PR_NUMBER" ]; then
    echo "Error: Missing arguments. Usage: ./1_analyze_ci_cd.sh <ACP_REPO_DIR> <PR_NUMBER>"
    exit 1
fi

cd "$ACP_REPO_DIR" || { echo "Error: Cannot navigate to $ACP_REPO_DIR"; exit 1; }

echo "--- Fetching CI/CD Status for PR #$PR_NUMBER ---"

# Get a count of failed checks
FAILED_COUNT=$(gh pr checks "$PR_NUMBER" --json state --jq '[.[] | select(.state == "FAILURE")] | length')

echo "TOTAL_FAILED_CHECKS=$FAILED_COUNT"

if [ "$FAILED_COUNT" -ge 2 ]; then
    echo "CRITICAL: CI/CD failure threshold met or exceeded."
    exit 0
fi

if [ "$FAILED_COUNT" -eq 1 ]; then
    echo "--- Fetching Logs for the Failed Check ---"
    # Find the name/ID of the failing run and fetch the log tail
    FAILED_RUN_ID=$(gh pr checks "$PR_NUMBER" --json bucket,state,link --jq '.[] | select(.state == "FAILURE") | .link' | grep -oP '\d+$')
    
    if [ -n "$FAILED_RUN_ID" ]; then
        gh run view "$FAILED_RUN_ID" --log-failed | tail -n 50
    else
        echo "Could not parse failed run ID to fetch logs."
    fi
fi
