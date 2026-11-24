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

"""Subprocess regression tests for inference-ref-arch deployment_test.sh scripts."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

_REPO_ROOT = Path(__file__).resolve().parents[8]
_PNG_1X1_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _ScriptSpec(NamedTuple):
    """Configuration for one online-inference deployment_test.sh target."""

    rel_script: str
    manifest_family: str
    accelerator: str
    model_id: str
    model_name: str
    kind: str


_TARGETS: tuple[_ScriptSpec, ...] = (
    _ScriptSpec(
        rel_script=(
            "test/scripts/platforms/gke/base/use-cases/inference-ref-arch/"
            "online-inference-tpu/max-diffusion/deployment_test.sh"
        ),
        manifest_family="online-inference-tpu/max-diffusion",
        accelerator="v5e",
        model_id="stabilityai/stable-diffusion-xl-base-1.0",
        model_name="stable-diffusion-xl-base-1-0",
        kind="diffusion",
    ),
    _ScriptSpec(
        rel_script=(
            "test/scripts/platforms/gke/base/use-cases/inference-ref-arch/"
            "online-inference-tpu/vllm/deployment_test.sh"
        ),
        manifest_family="online-inference-tpu/vllm",
        accelerator="v6e",
        model_id="google/gemma-3-1b-it",
        model_name="gemma-3-1b-it",
        kind="vllm",
    ),
    _ScriptSpec(
        rel_script=(
            "test/scripts/platforms/gke/base/use-cases/inference-ref-arch/"
            "online-inference-gpu/vllm/deployment_test.sh"
        ),
        manifest_family="online-inference-gpu/vllm",
        accelerator="l4",
        model_id="google/gemma-3-1b-it",
        model_name="gemma-3-1b-it",
        kind="vllm",
    ),
)


class DeploymentTestScriptsTest(unittest.TestCase):
    """Tests port-forward liveness, cleanup, and fail-fast payload checks."""

    def _stage_fake_repo(
        self,
        tmp_dir: str,
        spec: _ScriptSpec,
        *,
        kubectl_body: str,
        curl_body: str,
    ) -> tuple[Path, Path]:
        root = Path(tmp_dir)
        fake_repo = root / "repo"
        script_path = fake_repo / spec.rel_script
        script_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REPO_ROOT / spec.rel_script, script_path)

        config_dir = (
            fake_repo
            / "test/scripts/platforms/gke/base/use-cases/inference-ref-arch/config"
        )
        config_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            _REPO_ROOT
            / "test/scripts/platforms/gke/base/use-cases/inference-ref-arch"
            / "config/huggingface.sh",
            config_dir / "huggingface.sh",
        )

        shared_scripts = (
            fake_repo
            / "platforms/gke/base/use-cases/inference-ref-arch"
            / "terraform/_shared_config/scripts"
        )
        shared_scripts.mkdir(parents=True, exist_ok=True)
        (shared_scripts / "set_environment_variables.sh").write_text(
            'ira_online_tpu_kubernetes_namespace_name="ns-tpu"\n'
            'ira_online_gpu_kubernetes_namespace_name="ns-gpu"\n'
            f'HF_MODEL_NAME="{spec.model_name}"\n',
            encoding="utf-8",
        )

        overlay_dir = (
            fake_repo
            / "platforms/gke/base/use-cases/inference-ref-arch"
            / "kubernetes-manifests"
            / spec.manifest_family
            / f"{spec.accelerator}-{spec.model_name}"
        )
        overlay_dir.mkdir(parents=True, exist_ok=True)

        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        for name, body in (("kubectl", kubectl_body), ("curl", curl_body)):
            tool = bin_dir / name
            tool.write_text(body, encoding="utf-8")
            os.chmod(tool, 0o755)
        # Simulate container environments (.devcontainer, ci-cd/runner) without telnet.
        telnet_shim = bin_dir / "telnet"
        telnet_shim.write_text("#!/usr/bin/env bash\nexit 127\n", encoding="utf-8")
        os.chmod(telnet_shim, 0o755)

        return script_path, bin_dir

    def _run_script(
        self,
        script_path: Path,
        bin_dir: Path,
        extra_env: dict[str, str],
        timeout: float = 10.0,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env.pop("HF_MODEL_ID", None)
        env.pop("ACCELERATOR_TYPE", None)
        env.update(extra_env)
        return subprocess.run(
            ["bash", str(script_path)],
            env=env,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def test_succeeds_in_non_tty_session_and_cleans_up_port_forward(self) -> None:
        for spec in _TARGETS:
            with self.subTest(
                script=spec.rel_script
            ), tempfile.TemporaryDirectory() as tmp:
                pid_file = Path(tmp) / "pf.pid"
                args_log = Path(tmp) / "calls.log"
                png_fixture = Path(tmp) / "valid.png"
                png_fixture.write_bytes(_PNG_1X1_HEADER)

                kubectl_body = (
                    "#!/usr/bin/env bash\n"
                    f'printf "kubectl %s\\n" "$*" >> "{args_log}"\n'
                    f'echo "$$" > "{pid_file}"\n'
                    "exec sleep 30\n"
                )
                curl_body = (
                    "#!/usr/bin/env bash\n"
                    f'printf "curl %s\\n" "$*" >> "{args_log}"\n'
                    'out=""\n'
                    'url=""\n'
                    "while [[ $# -gt 0 ]]; do\n"
                    '  case "$1" in\n'
                    '    --output|-o) out="$2"; shift 2 ;;\n'
                    "    --data|-d|--header|-H|--request|-X|--max-time) shift 2 ;;\n"
                    '    http://*|https://*|http:/*) url="$1"; shift ;;\n'
                    "    *) shift ;;\n"
                    "  esac\n"
                    "done\n"
                    'if [[ "${url}" == *"/health" ]]; then exit 0; fi\n'
                    'if [[ "${url}" == *"/generate" ]]; then\n'
                    f'  cp "{png_fixture}" "${{out}}"\n'
                    "  exit 0\n"
                    "fi\n"
                    'if [[ "${url}" == *"/v1/models" ]]; then\n'
                    '  echo \'{"data":[{"id":"m"}]}\'\n'
                    "  exit 0\n"
                    "fi\n"
                    'if [[ "${url}" == *"/v1/chat/completions" ]]; then\n'
                    '  echo \'{"choices":[{"message":{"content":"Rayleigh scattering."}}]}\'\n'
                    "  exit 0\n"
                    "fi\n"
                    "exit 1\n"
                )
                script_path, bin_dir = self._stage_fake_repo(
                    tmp, spec, kubectl_body=kubectl_body, curl_body=curl_body
                )
                proc = self._run_script(
                    script_path,
                    bin_dir,
                    {
                        "ACCELERATOR_TYPE": spec.accelerator,
                        "HF_MODEL_ID": spec.model_id,
                    },
                )
                self.assertEqual(proc.returncode, 0, msg=proc.stderr + proc.stdout)
                calls = args_log.read_text(encoding="utf-8")
                self.assertIn("--address 127.0.0.1", calls)
                if spec.kind == "vllm":
                    self.assertNotIn("http:/127.0.0.1", calls)
                    self.assertIn(f'"/gcs/{spec.model_id}"', calls)

                pf_pid = int(pid_file.read_text(encoding="utf-8").strip())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pf_pid, 0)

    def test_exits_nonzero_when_port_forward_exits_early(self) -> None:
        for spec in _TARGETS:
            with self.subTest(
                script=spec.rel_script
            ), tempfile.TemporaryDirectory() as tmp:
                script_path, bin_dir = self._stage_fake_repo(
                    tmp,
                    spec,
                    kubectl_body="#!/usr/bin/env bash\nexit 1\n",
                    curl_body="#!/usr/bin/env bash\nexit 7\n",
                )
                proc = self._run_script(
                    script_path,
                    bin_dir,
                    {
                        "ACCELERATOR_TYPE": spec.accelerator,
                        "HF_MODEL_ID": spec.model_id,
                    },
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("exited unexpectedly", proc.stderr)

    def test_exits_nonzero_on_invalid_response_payload(self) -> None:
        for spec in _TARGETS:
            with self.subTest(
                script=spec.rel_script
            ), tempfile.TemporaryDirectory() as tmp:
                pid_file = Path(tmp) / "pf.pid"
                kubectl_body = (
                    "#!/usr/bin/env bash\n"
                    f'echo "$$" > "{pid_file}"\n'
                    "exec sleep 30\n"
                )
                curl_body = (
                    "#!/usr/bin/env bash\n"
                    'out=""\n'
                    'url=""\n'
                    "while [[ $# -gt 0 ]]; do\n"
                    '  case "$1" in\n'
                    '    --output|-o) out="$2"; shift 2 ;;\n'
                    "    --data|-d|--header|-H|--request|-X|--max-time) shift 2 ;;\n"
                    '    http://*) url="$1"; shift ;;\n'
                    "    *) shift ;;\n"
                    "  esac\n"
                    "done\n"
                    'if [[ "${url}" == *"/health" ]]; then exit 0; fi\n'
                    'if [[ "${url}" == *"/generate" ]]; then\n'
                    '  printf \'{"detail":"internal error"}\' > "${out}"\n'
                    "  exit 0\n"
                    "fi\n"
                    'if [[ "${url}" == *"/v1/models" ]]; then\n'
                    '  echo \'{"data":[{"id":"m"}]}\'\n'
                    "  exit 0\n"
                    "fi\n"
                    'echo \'{"choices":[{"message":{"content":""}}]}\'\n'
                )
                script_path, bin_dir = self._stage_fake_repo(
                    tmp, spec, kubectl_body=kubectl_body, curl_body=curl_body
                )
                try:
                    proc = self._run_script(
                        script_path,
                        bin_dir,
                        {
                            "ACCELERATOR_TYPE": spec.accelerator,
                            "HF_MODEL_ID": spec.model_id,
                        },
                    )
                    self.assertNotEqual(proc.returncode, 0)
                    pf_pid = int(pid_file.read_text(encoding="utf-8").strip())
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pf_pid, 0)
                finally:
                    if pid_file.exists():
                        try:
                            os.kill(
                                int(pid_file.read_text(encoding="utf-8").strip()),
                                signal.SIGKILL,
                            )
                        except ProcessLookupError:
                            pass

    def test_exits_nonzero_when_accelerator_type_empty(self) -> None:
        for spec in _TARGETS:
            with self.subTest(
                script=spec.rel_script
            ), tempfile.TemporaryDirectory() as tmp:
                script_path, bin_dir = self._stage_fake_repo(
                    tmp,
                    spec,
                    kubectl_body="#!/usr/bin/env bash\nexit 0\n",
                    curl_body="#!/usr/bin/env bash\nexit 0\n",
                )
                proc = self._run_script(script_path, bin_dir, {"ACCELERATOR_TYPE": ""})
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("ACCELERATOR_TYPE is not set", proc.stderr)


if __name__ == "__main__":
    unittest.main()
