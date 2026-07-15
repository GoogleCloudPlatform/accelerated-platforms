# LLM-D Skills and Evaluation Suite

This directory contains the source definitions, configurations, and evaluation
tests for the LLM-D benchmarking and deployment skills.

## Directory Structure

```text
skills/
├── llm-d-benchmarking/          # Combined benchmark skill using standard workload profiles
│   └── evals/
│       └── evals.json           # Scenarios for benchmarking
├── llm-d-deploy-stack/          # Skill to deploy the GKE + vLLM stack
│   └── evals/
│       └── evals.json           # Scenarios for deploy-stack
├── llm-d-workload-tuner/        # (Experimental) Workload tuning recommendation engine skill
│   ├── evals/
│   │   └── evals.json           # Scenarios for workload-tuner
│   ├── references/
│   │   └── llm-d-workload-profiles.md
│   └── scripts/
│       └── tune_workload.py     # Workload tuner Python entrypoint
├── scripts/
│   ├── helper-pods/             # Manifests and scripts for helper pods
│   └── run_benchmark.sh         # Consolidated benchmark shell harness
├── requirements-eval.txt        # Evaluation python requirements (empty/placeholder)
```

---

## The Evaluation Runner (`evaluate.py`)

The evaluation runner
([evaluate.py](${ACP_REPO_DIR}/test/scripts/skills-eval/evaluate.py)) automates
testing of the repository's shell scripts and configuration validations. It maps
test cases defined in each skill's `evals/evals.json` file to programmatic
assertions, verifying correctness without modifying your local GCP state.

### How Mock Mode Works (`--mock`)

When executed with `--mock`, the script:

1.  Creates a sandbox directory
    `${ACP_REPO_DIR}/skills-eval-workspace/mock-bin`.
2.  Dynamically writes mock wrapper binaries for `gcloud`, `kubectl`, `curl`,
    and `llm-d`.
3.  Injects the mock binary directory at the front of the subprocess execution
    `PATH`.
4.  Logs all CLI commands called during execution to
    `skills-eval-workspace/mock_calls.log`.
5.  Emulates the expected outputs of CLI commands (e.g. mock custom compute
    classes list, model status JSONs, Managed Prometheus configuration state).
6.  Cleans up environment changes and output files after completion.

---

## Running the Evaluations

### Prerequisites

The runner requires Python 3.12+ (standard library modules only).

### Local Execution (Mock Mode)

To run the mock evaluations locally:

```bash
python3 ${ACP_REPO_DIR}/test/scripts/skills-eval/evaluate.py --mock
```

This will automatically discover and run all test scenarios across all skill
directories in under a second and output a summary table of passed/failed
assertions.

### Reviewing Results

Upon execution completion, the runner aggregates duration, token estimates, and
assertion status details into a benchmark report:

- **Report Path**:
  `${ACP_REPO_DIR}/skills-eval-workspace/iteration-1/benchmark.json`

---

## Adding New Test Cases

Test cases are loaded from the `evals/evals.json` list inside each skill's
directory. To add a new test scenario:

1.  Open the target skill's configuration file (e.g.,
    `${ACP_REPO_DIR}/skills/llm-d-deploy-stack/evals/evals.json`).
2.  Append a new JSON object to the list:
    ```json
    [
      ...
      {
        "id": 4,
        "prompt": "Test prompt describing the action",
        "expected_output": "Expected text output summary",
        "assertions": [
          "The platform_name is updated to 'my-cluster' in platforms/gke/base/_shared_config/platform.auto.tfvars",
          "A gcloud container clusters describe command was run to check managedPrometheusConfig"
        ]
      }
    ]
    ```
3.  Ensure that the assertion string matches a checker pattern in
    `check_assertion()` inside
    [evaluate.py](test/scripts/skills-eval/evaluate.py).
