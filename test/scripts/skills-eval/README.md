# LLM-D Skills Evaluation Runner

The `evaluate.py` script is a test runner designed to validate the behavior of
LLM-D skills (such as deployment and benchmarking scripts) without interacting
with actual Google Cloud resources.

## Running the Evaluations

To run the evaluations in mock mode, execute the following command from the
repository root:

```bash
python3 test/scripts/skills-eval/evaluate.py --mock
```

This will:

1. Autodiscover all evaluation scenarios defined in `skills/*/evals/evals.json`.
2. Run each scenario in a mocked CLI environment.
3. Print the results of programmatic assertions.
4. Save a summary report to `skills-eval-workspace/iteration-1/benchmark.json`.

You can also run evaluations for a specific skill by pointing to its evaluation
file:

```bash
python3 test/scripts/skills-eval/evaluate.py --mock --eval-file skills/llm-d-deploy-stack/evals/evals.json
```

## How Mock Mode Works

When running with the `--mock` flag, `evaluate.py` sets up a local sandbox to
simulate GCP and Kubernetes environments:

1. **Mock Binaries**: It creates a temporary directory
   `skills-eval-workspace/mock-bin` and populates it with Python scripts
   mimicking:
   - `gcloud`
   - `kubectl`
   - `curl`
   - `llm-d`
2. **PATH Manipulation**: It prepends this temporary directory to the `PATH`
   environment variable for child processes. When the skill scripts execute,
   they call these mock binaries instead of the real tools.
3. **State Simulation**: The mock binaries (`gcloud`, `kubectl`, `curl`, and
   `llm-d`) return predefined outputs matching expected scenarios (e.g.,
   simulating cluster description, metric lists, or model service availability).
4. **Call Logging**: All invocations of the mock binaries are logged to
   `skills-eval-workspace/mock_calls.log`. The runner uses this log to verify
   that specific commands were executed with the correct arguments.
5. **Cleanup**: After the tests complete, the temporary mock binaries are
   deleted, and any environment modifications are reverted.

## Assertions Checked

The runner verifies the correctness of skills by checking:

- File modifications (e.g., verifying `platform.auto.tfvars` is updated
  correctly).
- Script invocation arguments (e.g., verifying `configure_and_validate.sh` is
  called with correct model/accelerator).
- Output verification (e.g., checking stdout/stderr for specific messages,
  warnings for unsupported hardware).
- Command execution history (by parsing `mock_calls.log` to ensure commands like
  `gcloud container clusters describe` or `curl` were executed).
