---
name: ai-review-for-pull-requests
description: An AI-driven PR reviewer for the accelerated-platforms repository. Prompts the user for inputs, validates CI/CD thresholds, enforces coding standards, and challenges architectural drift against gemini.md.
version: 0.1.0
allowed-tools: gh git jq cat
---

# AI Pull Request Reviewer Skill

Follow these instructions to automatically review a Pull Request in the `accelerated-platforms` repository.

## 1. Gather User Inputs

Before beginning the review process, you MUST ask the user for the following information if it is not already provided in their prompt:

- **ACP_REPO_DIR**: The local file path to the `accelerated-platforms` repository.
- **PR_NUMBER**: The GitHub Pull Request number they want you to review.

_Do not proceed until both of these values are provided._

## 2. CI/CD Gatekeeper Check

Once you have the inputs, run `scripts/1_analyze_ci_cd.sh <ACP_REPO_DIR> <PR_NUMBER>` to fetch the status of the GitHub workflows and CI/CD tests.

- **Analyze the Output**: The script will output the number of failed checks and the logs for those failures.
- **Rule (>= 2 Failures OR ci-cd tests not completed)**: If there are 2 or more failed tests or the ci-cd tests are not completed, **STOP YOUR REVIEW IMMEDIATELY**. Output a message to the user stating: _"There are [X] broken CI/CD pipelines. Please fix the broken tests before requesting an AI code review."_ Do not proceed to Step 3.
- **Rule (< 2 Failures)**: If there are 0 or 1 failed tests, summarize the root cause of the failure based on the fetched logs, append this summary to your internal notes for the final report, and proceed to Step 3.

## 3. Context Gathering & AI Analysis

Run `scripts/2_fetch_context.sh <ACP_REPO_DIR> <PR_NUMBER>` to extract the PR's code diff and the contents of the `gemini.md` architecture document.

**Perform your internal reasoning on the diff:**

1.  **Coding Standards**: Look for violations, security vulnerabilities, or anti-patterns not typically caught by automated CI/CD linters.
2.  **Architectural Alignment**: Compare the changes against the rules and guidelines defined in `gemini.md`.
3.  **Actionable Recommendations**: Formulate specific code snippets to fix identified issues.
4.  **Challenge Choices**: If a change explicitly violates `gemini.md`, draft a firm but constructive challenge to the developer's architectural choice.

## 4. Construct and Submit Review

Using the insights from Step 3, compile a comprehensive Markdown summary report. Save your report locally, then run `scripts/3_submit_review.sh <ACP_REPO_DIR> <PR_NUMBER> <path_to_markdown_review_body.md>` to post your review to GitHub.

The review body must include:

- **CI/CD Summary**: (If there was 1 failure).
- **Architectural Feedback**: Challenges based on `gemini.md`.
- **Code Quality Recommendations**: Specific fixes.
