#!/usr/bin/env python3
"""
Local CI Runner based on Cloud Build Terraform Triggers.

1. Parses google_cloudbuild_trigger blocks from a .tf file using hcl2.
2. Gets changed files from git diff compared to a target branch.
3. Matches changed files against each trigger's included_files / ignored_files.
4. Executes the corresponding local CI build/test for matched triggers.
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import hcl2
except ImportError:
    print("ERROR: python-hcl2 package is required.")
    sys.exit(1)


def parse_tf_triggers(tf_path: Path) -> list[dict]:
    """Parse Terraform triggers using python-hcl2."""
    triggers = []
    with open(tf_path, 'r') as f:
        data = hcl2.load(f)

    resources = data.get('resource', [])
    for res in resources:
        if 'google_cloudbuild_trigger' in res:
            for name, config in res['google_cloudbuild_trigger'].items():
                filename = config.get('filename', [None])[0] if isinstance(config.get('filename'), list) else config.get('filename')
                included_files = config.get('included_files', [])
                ignored_files = config.get('ignored_files', [])
                substitutions = config.get('substitutions', [{}])[0]

                # Normalize lists if hcl2 outputs nested structures
                if included_files and isinstance(included_files[0], list):
                    included_files = included_files[0]
                if ignored_files and isinstance(ignored_files[0], list):
                    ignored_files = ignored_files[0]

                triggers.append({
                    'name': name,
                    'filename': filename,
                    'included_files': included_files,
                    'ignored_files': ignored_files,
                    'substitutions': substitutions
                })
    return triggers


def get_git_changed_files(base_ref: str) -> list[str]:
    """Retrieve list of modified/added files compared to base branch."""
    try:
        # Check against base branch/ref
        cmd = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        changed = [line.strip() for line in output.splitlines() if line.strip()]

        # Include uncommitted local staged/unstaged changes
        uncommitted_cmd = ["git", "status", "--porcelain"]
        uncommitted_output = subprocess.check_output(uncommitted_cmd, text=True)
        for line in uncommitted_output.splitlines():
            if line.strip():
                filepath = line.strip().split()[-1]
                if filepath not in changed:
                    changed.append(filepath)

        return changed
    except subprocess.CalledProcessError as e:
        print(f"Error fetching git diff: {e}")
        sys.exit(1)


def is_file_matching_patterns(filepath: str, glob_patterns: list[str]) -> bool:
    """Check if a filepath matches Cloud Build glob pattern."""
    for pattern in glob_patterns:
        # CloudBuild ** syntax translates differently than standard python glob
        regex_pat = fnmatch.translate(pattern).replace(r'/\*', r'/.*').replace(r'\*', r'[^/]*')
        if re.match(regex_pat, filepath):
            return True
    return False


def is_trigger_relevant(trigger: dict, changed_files: list[str]) -> tuple[bool, list[str]]:
    """Determine if a trigger should run based on changed files."""
    inc_patterns = trigger.get('included_files', [])
    ign_patterns = trigger.get('ignored_files', [])

    matched_files = []
    for f in changed_files:
        if inc_patterns and not is_file_matching_patterns(f, inc_patterns):
            continue
        if ign_patterns and is_file_matching_patterns(f, ign_patterns):
            continue
        matched_files.append(f)

    return len(matched_files) > 0, matched_files


def run_trigger_locally(trigger: dict, dry_run: bool = False):
    """Execute the build config associated with the trigger."""
    config_file = trigger.get('filename')
    print(f"\nRunning Trigger: [{trigger['name']}]")

    if not config_file or not os.path.exists(config_file):
        print(f"   WARNING: CloudBuild file '{config_file}' not found locally. Skipping execution.")
        return

    cmd = ["cloud-build-local", f"--config={config_file}"]

    # Pass substitutions if they exist
    subs = trigger.get('substitutions', {})
    if subs:
        sub_str = ",".join([f"{k}={v}" for k, v in subs.items()])
        cmd.append(f"--substitutions={sub_str}")
        
    cmd.append(".")

    print(f"   Command: {' '.join(cmd)}")
    if dry_run:
        print("   [Dry Run] Skipping actual execution. (Note: cloud-build-local is deprecated by Google)")
        return

    try:
        subprocess.run(cmd, check=True)
        print(f"SUCCESS: Trigger [{trigger['name']}] finished successfully.")
    except FileNotFoundError:
        print(f"ERROR: 'cloud-build-local' executable not found in PATH.")
        print("Note: cloud-build-local is deprecated. For local testing without it, inspect the cloudbuild.yaml and run steps manually.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Trigger [{trigger['name']}] failed with exit code {e.returncode}.")


def main():
    parser = argparse.ArgumentParser(description="Replicate CloudBuild Triggers locally.")
    parser.add_argument(
        "--tf-file",
        default="test/ci-cd/terraform/cloudbuild/cloudbuild_trigger.tf",
        help="Path to cloudbuild_trigger.tf file"
    )
    parser.add_argument(
        "--base-branch",
        default="origin/main",
        help="Target base branch to compare diff against (default: origin/main)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matching triggers without executing builds"
    )

    args = parser.parse_args()
    tf_path = Path(args.tf_file)

    if not tf_path.exists():
        # Fallback to check if it's relative to root or we are somewhere else
        # Just warn and exit gracefully for the ci suite
        print(f"WARNING: Terraform file not found at {tf_path}. Skipping trigger checks.")
        sys.exit(0)

    triggers = parse_tf_triggers(tf_path)
    print(f"Loaded {len(triggers)} trigger definitions from {tf_path}")

    changed_files = get_git_changed_files(args.base_branch)
    if not changed_files:
        print(f"No changes detected relative to {args.base_branch}. Exiting.")
        sys.exit(0)

    print(f"Detected {len(changed_files)} changed file(s). Evaluating triggers...\n")

    executed_count = 0
    for trigger in triggers:
        relevant, matched_files = is_trigger_relevant(trigger, changed_files)
        if relevant:
            executed_count += 1
            print(f"Matched Trigger: {trigger['name']}")
            print(f"   Matches: {', '.join(matched_files[:3])}" + ("..." if len(matched_files) > 3 else ""))
            run_trigger_locally(trigger, dry_run=args.dry_run)

    if executed_count == 0:
        print("No triggers matched current file changes.")


if __name__ == "__main__":
    main()
