---
trigger: always_on
---

# GEMINI.MD: AI Collaboration Guide

This document provides essential context for AI models interacting with this
project. Adhering to these guidelines will ensure consistency and maintain code
quality.

## 1. Project Overview & Purpose

- **Primary Goal:** This repository is a collection of best practices, reference
  architectures, example use cases, and reference implementations for
  accelerated platforms on Google Cloud. It focuses on leveraging GPUs (Graphics
  Processing Units) and TPUs (Tensor Processing Units) for computationally
  intensive tasks like machine learning, data analysis, and AI.
- **Business Domain:** Cloud Infrastructure, High-Performance Computing (HPC),
  AI/ML Operations (MLOps), and Infrastructure as Code (IaC).

## 2. Core Technologies & Stack

- **Languages:** Python (primarily 3.12+), Terraform (HCL), Bash, and some
  JavaScript/TypeScript for specific components (e.g., packages).
- **Frameworks & Runtimes:**
  - **Orchestration:** Google Kubernetes Engine (GKE) is the primary runtime for
    workloads.
  - **Accelerators:** Support for NVIDIA GPUs (L4, H100, H200, RTX 6000) and
    Google TPUs (v5e, v6e).
  - **Inference Engines:** vLLM, MaxDiffusion, Diffusers.
- **Infrastructure:** Terraform for provisioning Google Cloud resources.
- **Containerization:** Docker/OCI-compliant containers.
- **Package Manager(s):** pip (Python), npm (for specific node_modules in some
  directories).

## 3. Architectural Patterns

- **Overall Architecture:** A modular reference implementation architecture. It
  separates reusable modules (Infrastructure), platform configurations (GKE,
  Cloud Workstations), and specific use cases (Inference, Training, Federated
  Learning).
- **Directory Structure Philosophy:**
  - `/docs`: Detailed documentation and architecture guides.
  - `/modules`: Reusable Terraform modules for infrastructure.
  - `/platforms`: Foundational platform implementations (e.g., GKE Base, Cloud
    Workstations).
  - `/use-cases`: Specific implementations and configurations for various
    workloads.
  - `/terraform`: Root Terraform configurations for deploying reference
    architectures.
  - `/container-images`: Source code and build scripts for custom container
    images.

## 4. Coding Conventions & Style Guide

- **Formatting:\*** **General:** Indentation is 2 spaces for most files, except
  for **Python files which use 4 spaces**. Files should use UTF-8 charset, LF
  line endings, and include a final newline. Trailing whitespace is trimmed
  (except in Markdown).\* **Python:** Strictly follows **Black** for formatting
  and **isort** for import organization. **Markdown/JSON:** Uses **Prettier**
  for consistent formatting. See `.prettierrc` for configuration. **Terraform:**
  Must use `terraform fmt` and follow Google Cloud's Terraform best practices.
  **Dictionaries:** should always be alphabetized by key. **Spelling:** Uses
  **CSpell** for spell checking with custom dictionaries defined in
  `cspell.json`. **Terraform:** Must use `terraform fmt` and follow Google
  Cloud's Terraform best practices. **New Variables:** New variables should
  always be updated alphabetically

- **Naming Conventions:**
  - **Files:** kebab-case is standard for documentation and configuration files.
  - **Terraform:** Standard HCL naming conventions (snake_case for resource
    names and variables).
  - **Kubernetes:** Standard manifest naming (kebab-case).
- **API Design:** Focuses on standard interfaces for inference (e.g.,
  OpenAI-compatible endpoints via vLLM).
- **Error Handling:** Standard Python exception handling; Kubernetes-native
  health checks and logging for service stability.

## 5. Key Files & Entrypoints

- **Main Entrypoint(s):**
  - Terraform: Root modules in `/terraform/`.
  - Kubernetes: Entrypoints often defined in `kustomization.yaml` files within
    use-case directories.
- **Configuration:**
  - `.devcontainer/`: Defines the VS Code Dev Container environment.
  - `.editorconfig`: Defines whitespace, indentation, and encoding standards.
  - `.prettierrc`: Prettier configuration for non-code files.
  - `cspell.json`: Configuration for spell checking and custom dictionaries.
- **CI/CD Pipeline:** GitHub Actions workflows located in `.github/workflows/`
  (e.g., `lint.yml`, `terraform.yml`, `python-test.yml`).

## 6. Development & Testing Workflow

- **Local Development Environment:** Standardized using **Visual Studio Code Dev
  Containers**. This environment pre-installs all necessary tools (gcloud,
  terraform, python, etc.).
- **Testing:**
  - **Python:** Run tests via standard test runners (e.g., `pytest`). Coverage
    scripts like `run_python_coverage_test.sh` are available.
  - **Infrastructure:** Terraform validation and linting are part of the CI
    process.
- **CI/CD Process:** Automated linting, formatting checks, and unit tests are
  triggered on pull requests and commits to the main branch. When implementing
  new features, **verify if they are covered in `test/ci-cd` and
  `test/terraform`** and update scripts as needed to maintain or improve
  coverage.

## 7. Specific Instructions for AI Collaboration

- **Contribution Guidelines:** All contributions require a **Contributor License
  Agreement (CLA)**. Submissions must be via GitHub Pull Requests and require
  peer review as outlined in `CONTRIBUTING.md`.
- **Pull Request Pattern:** When creating a Pull Request, follow this structure:

  - **Title:** Concise summary of the change.
  - **Overview:** Brief description of the purpose of the PR.
  - **Key Changes:** Bulleted list of the main modifications.
  - **Impact of Change:** Analysis of how this change affects the system,
    performance, or users.
  - **References:** Links to related issues, documentation, or external
    resources.

- **Kubernetes & Kustomize:** Always follow the **Kustomize structure** to
  templatize and create overlays with an `env` file. Perform validation steps
  (e.g., `kustomize build`) and output the results to a file for additional
  review to ensure overlays are not being overwritten.
- **Infrastructure (IaC):** Changes to files in `/terraform` or `/modules`
  modify cloud infrastructure. These must be rigorously validated with
  `terraform plan` and reviewed for security and cost impact.
- **Security:** **Do not hardcode secrets, API keys, or credentials.** Use
  environment variables or secret management services (e.g., Google Cloud Secret
  Manager).
- **Dependencies:** Add Python dependencies to `requirements.txt` or
  `pyproject.toml` (if present). For Terraform, ensure provider versions are
  locked.
- **Commit Messages:** Follow the **Conventional Commits** specification (e.g.,
  `feat:`, `fix:`, `docs:`, `chore:`).

  **Skills Development Rules:**

  - When creating or modifying an agent skill, you **must** create a
    corresponding `evals/evals.json` scenario list in the skill's subdirectory
    containing standard test prompts and expected assertions.
  - Update
    [skills/scripts/evaluate.py](accelerated-platforms/skills/scripts/evaluate.py)
    to parse any new custom assertions.
  - Run the mock evaluations (`python3 skills/scripts/evaluate.py --mock`)
    locally and ensure a 100% success rate before committing changes.

## 8. Common Anti-Patterns & Best Practices (From PR Feedback)

When contributing to the repository, especially via AI-assisted generation,
avoid the following common anti-patterns:

- **Declarative Infrastructure over Imperative Hacks:**

  - **Anti-Pattern:** Modifying base Kubernetes `deployment.yaml` manifests to
    inject imperative shell wrappers (like `/bin/sh -c`) to parse dynamic
    runtime variables.
  - **Best Practice:** Rely on **Kustomize JSON Patches** to inject runtime
    arguments directly into the container spec at the overlay level, keeping
    base templates declarative and clean.

- **Meaningful Naming over Dictionary Pollution:**

  - **Anti-Pattern:** Lazily adding abbreviation shorthand (e.g., `kust`) to
    `.github/workflows/dictionary/llmdskills.txt` to bypass `cspell` errors.
  - **Best Practice:** Rename shorthand variables to descriptive, plain-English
    terms (e.g., `kustomization_data`). Only add genuine domain-specific jargon
    to the dictionary, and ensure the dictionary remains alphabetically sorted.

- **Single Source of Truth & Self-Documenting Code:**

  - **Anti-Pattern:** Hardcoding redundant parameters (like `EXTRA_ARGS`) in
    multiple `runtime.env` files across different hardware overlays, and leaving
    monolithic Python scripts undocumented.
  - **Best Practice:** Centralize configuration logic within programmatic tuners
    (acting as the single source of truth) and eliminate hardcoded entries.
    Always add comprehensive docstrings to Python functions detailing their
    purpose, inputs, and outputs.

- **Test-Driven Validation Before Commits:**

  - **Anti-Pattern:** Creating commits and pushing changes (e.g., agent skill
    definitions or sizing scripts) without verifying them locally, leading to
    broken CI mock tests.
  - **Best Practice:** Define rigorous testing scenarios in `evals/evals.json`
    and validate changes locally using
    `python3 test/scripts/skills-eval/evaluate.py --mock`, ensuring a 100%
    success rate before committing.

- **Strict Formatting and Clean Git Hygiene:**
  - **Anti-Pattern:** Pushing multiple minor "fix typo" or "formatting" commits
    that clutter the PR, or pushing code that fails standard repo formatters.
  - **Best Practice:** Use `git commit --amend` to squash iterative changes into
    a single, cohesive commit. Enforce strict pre-commit formatting with `black`
    and `isort` for Python, and `prettier@3.4.2` for JSON/Markdown/YAML.
