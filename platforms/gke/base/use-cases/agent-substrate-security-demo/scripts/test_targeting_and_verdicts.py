# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for cluster targeting, pinned kubeconfigs, and teardown guards."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BASE_DIR = Path(__file__).resolve().parent.parent
for _p in (str(BASE_DIR / "ui"), str(BASE_DIR / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import kube
import server


class ClusterTargetingAndTeardownGuardsTest(unittest.TestCase):
    """Verifies staged.env precedence, pinned UI kubeconfig, and shell guards."""

    def setUp(self) -> None:
        kube.reset_caches()

    def tearDown(self) -> None:
        kube.reset_caches()

    def test_staged_env_outranks_mismatched_ambient_kube_context(self) -> None:
        def _mismatched_kubectl(args: list[str], **_kw: object) -> tuple[str, str, int]:
            if args[:3] == ["kubectl", "config", "current-context"]:
                return ("gke_other-proj_us-west1_prod-cluster", "", 0)
            return ("", "", 0)

        with (
            mock.patch.dict(
                os.environ,
                {"CLUSTER_NAME": "", "PROJECT_ID": "", "KUBE_CONTEXT": ""},
                clear=False,
            ),
            mock.patch.object(
                kube,
                "_load_staged_defaults",
                return_value={
                    "PROJECT_ID": "staged-proj",
                    "CLUSTER_LOCATION": "us-central1-b",
                    "CLUSTER_NAME": "staged-cluster",
                },
            ),
            mock.patch.object(kube, "run_cmd", side_effect=_mismatched_kubectl),
        ):
            self.assertEqual(kube.get_cluster_name(), "staged-cluster")
            self.assertEqual(kube.detect_project_id(), "staged-proj")

    def test_pin_staged_kubeconfig_writes_private_file_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as kc_dir:
            staged_map = {
                "PROJECT_ID": "p1",
                "CLUSTER_LOCATION": "us-central1-b",
                "CLUSTER_NAME": "c1",
            }
            with (
                mock.patch.dict(
                    os.environ, {"CLUSTER_NAME": "", "KUBE_CONTEXT": ""}, clear=False
                ),
                mock.patch.object(kube, "STATE_DIR", Path(kc_dir)),
                mock.patch.object(
                    kube, "_load_staged_defaults", return_value=staged_map
                ),
                mock.patch.object(
                    kube, "run_cmd", return_value=("apiVersion: v1", "", 0)
                ),
            ):
                kc_file = server.pin_staged_kubeconfig()
                self.assertTrue(kc_file.endswith("ui.kubeconfig"))
                self.assertEqual(Path(kc_file).stat().st_mode & 0o777, 0o600)
                self.assertEqual(kube._env().get("KUBECONFIG"), kc_file)
                with (
                    mock.patch.object(
                        kube, "run_cmd", return_value=("", "missing ctx", 1)
                    ),
                    self.assertRaises(kube.UpstreamCommandError),
                ):
                    server.pin_staged_kubeconfig()

    def test_shell_common_and_teardown_refuse_wrong_context_and_option_b(self) -> None:
        scripts_dir = BASE_DIR / "scripts"
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            uc_copy = td_p / "uc"
            (uc_copy / "scripts").mkdir(parents=True)
            for name in ("common.sh", "port-forward.sh", "teardown.sh"):
                dst = uc_copy / "scripts" / name
                dst.write_text(
                    (scripts_dir / name).read_text(encoding="utf-8"), encoding="utf-8"
                )
                dst.chmod(0o755)

            bin_p = td_p / "bin"
            bin_p.mkdir()
            (bin_p / "kubectl").write_text(
                "\n".join(
                    ["#!/usr/bin/env bash", 'echo "gke_other-proj_us-west1_prod"']
                )
                + "\n",
                encoding="utf-8",
            )
            (bin_p / "gcloud").write_text(
                "\n".join(["#!/usr/bin/env bash", 'echo "my-proj"']) + "\n",
                encoding="utf-8",
            )
            for b in (bin_p / "kubectl", bin_p / "gcloud"):
                b.chmod(0o755)

            env = {**os.environ, "PATH": f"{bin_p}:{os.environ.get('PATH', '')}"}
            for k in ("CLUSTER_NAME", "PROJECT_ID", "CLUSTER_LOCATION"):
                env.pop(k, None)

            common_sh = uc_copy / "scripts" / "common.sh"
            no_state = td_p / "no-state"
            r_mismatch = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{common_sh}" && resolve_demo_target "{no_state}"',
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(r_mismatch.returncode, 0)

            st_dir = uc_copy / ".state"
            st_dir.mkdir()
            (st_dir / "staged.env").write_text(
                "\n".join(
                    [
                        "PROJECT_ID=staged-p",
                        "CLUSTER_NAME=staged-c",
                        "CLUSTER_LOCATION=us-central1-b",
                        "PROVISION_GCP_INFRA=false",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            r_staged = subprocess.run(
                [
                    "bash",
                    "-c",
                    (
                        f'source "{common_sh}" && resolve_demo_target "{st_dir}" '
                        '&& echo "$PROJECT_ID/$CLUSTER_NAME"'
                    ),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(r_staged.returncode, 0, r_staged.stderr)
            self.assertEqual(r_staged.stdout.strip(), "staged-p/staged-c")

            # Option B (PROVISION_GCP_INFRA=false) must be refused by teardown.sh
            r_opt_b = subprocess.run(
                [str(uc_copy / "scripts" / "teardown.sh"), "--yes"],
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(r_opt_b.returncode, 0)
            self.assertIn("teardown-standard.sh", r_opt_b.stderr)

            # Non-interactive teardown without --yes must fail closed
            (st_dir / "staged.env").write_text(
                "\n".join(
                    [
                        "PROJECT_ID=staged-p",
                        "CLUSTER_NAME=staged-c",
                        "CLUSTER_LOCATION=us-central1-b",
                        "PROVISION_GCP_INFRA=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            r_no_yes = subprocess.run(
                [str(uc_copy / "scripts" / "teardown.sh")],
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(r_no_yes.returncode, 0)
            self.assertIn("--yes", r_no_yes.stderr)


if __name__ == "__main__":
    unittest.main()
