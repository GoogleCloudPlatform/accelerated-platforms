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

"""Unit tests for TorchTitan TPU SFT Kustomize manifests, ComputeClass, and docs."""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[8]
MANIFESTS_ROOT = (
    REPO_ROOT / "platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests"
)
DOCS_ROOT = REPO_ROOT / "docs/platforms/gke/base/use-cases/training-ref-arch"
COMPUTE_CLASS_DIR = (
    REPO_ROOT
    / "platforms/gke/base/core/custom_compute_class/templates/manifests/tpu/v6e"
)

SAMPLE_ENV = {
    "sft_tpu_torchtitan_image_url": "europe-west4-docker.pkg.dev/example-proj/trn/torchtitan-tpu-sft:0.3.0",
    "sft_tpu_torchtitan_single_host_kubernetes_namespace_name": "trn-sft-tpu-torchtitan-sh",
    "sft_tpu_torchtitan_single_host_kubernetes_service_account_name": "trn-sft-tpu-torchtitan-sa",
    "sft_tpu_torchtitan_single_host_dataset_bucket_name": "example-proj-trn-tt-sft-sh",
    "sft_tpu_torchtitan_multi_host_kubernetes_namespace_name": "trn-sft-tpu-torchtitan-mh",
    "sft_tpu_torchtitan_multi_host_kubernetes_service_account_name": "trn-sft-tpu-torchtitan-sa",
    "sft_tpu_torchtitan_multi_host_dataset_bucket_name": "example-proj-trn-tt-sft-mh",
    "huggingface_hub_models_bucket_name": "example-proj-trn-hf-models",
    "HF_MODEL_ID": "google/gemma-4-12B-it",
    "HF_MODEL_NAME": "gemma-4-12b-it",
}


def _render_runtime_env(tpl_text: str, values: dict[str, str]) -> str:
    rendered = tpl_text
    for key, val in values.items():
        rendered = rendered.replace(f"${{{key}}}", val)
    unreplaced = re.findall(r"\$\{[^}]+\}", rendered)
    if unreplaced:
        raise ValueError(f"Unreplaced template variables: {unreplaced}")
    return rendered


def _kustomize_render(family_dir: Path, overlay_name: str) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        copied = Path(tmp) / family_dir.name
        shutil.copytree(family_dir, copied)
        tpl_path = copied / "base/templates/runtime.tpl.env"
        (copied / "base/runtime.env").write_text(
            _render_runtime_env(tpl_path.read_text(encoding="utf-8"), SAMPLE_ENV),
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["kubectl", "kustomize", str(copied / overlay_name)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "replaced-by-kustomize" not in proc.stdout, proc.stdout
        return [doc for doc in yaml.safe_load_all(proc.stdout) if doc is not None]


class TorchTitanSftManifestsTest(unittest.TestCase):
    """Validates rendered Kustomize overlays, ComputeClass, and doc paths."""

    def test_compute_class_v6e_hyperdisk_and_4x4_schema(self) -> None:
        expected = {
            "custom-compute-tpu-v6e-2x2.yaml": (
                "tpu-v6e-2x2",
                "ct6e-standard-4t",
                4,
                "2x2",
            ),
            "custom-compute-tpu-v6e-2x4.yaml": (
                "tpu-v6e-2x4",
                "ct6e-standard-8t",
                8,
                "2x4",
            ),
            "custom-compute-tpu-v6e-4x4.yaml": (
                "tpu-v6e-4x4",
                "ct6e-standard-4t",
                4,
                "4x4",
            ),
        }
        for filename, (name, machine, count, topology) in expected.items():
            with self.subTest(filename=filename):
                doc = yaml.safe_load(
                    (COMPUTE_CLASS_DIR / filename).read_text(encoding="utf-8")
                )
                self.assertEqual(doc["kind"], "ComputeClass")
                self.assertEqual(doc["metadata"]["name"], name)
                priorities = doc["spec"]["priorities"]
                self.assertGreaterEqual(len(priorities), 4)
                for rule in priorities:
                    self.assertEqual(rule["machineType"], machine)
                    self.assertEqual(
                        rule["storage"]["bootDiskType"], "hyperdisk-balanced"
                    )
                    self.assertEqual(
                        rule["tpu"],
                        {
                            "count": count,
                            "topology": topology,
                            "type": "tpu-v6e-slice",
                        },
                    )

    def test_single_host_overlay_invariants(self) -> None:
        docs = _kustomize_render(
            MANIFESTS_ROOT / "sft-tpu-torchtitan-single-host",
            "v6e-2x2-gemma-4-12b-lora",
        )
        jobs = [d for d in docs if d["kind"] == "Job"]
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["metadata"]["name"], "tt-sft-sh-v6e-2x2-gemma-4-12b")
        self.assertLessEqual(len(job["metadata"]["name"]) + 6, 63)

        pod_spec = job["spec"]["template"]["spec"]
        self.assertTrue(pod_spec["hostNetwork"])
        self.assertEqual(pod_spec["dnsPolicy"], "ClusterFirstWithHostNet")
        self.assertEqual(
            pod_spec["nodeSelector"],
            {
                "cloud.google.com/compute-class": "tpu-v6e-2x2",
                "cloud.google.com/gke-tpu-accelerator": "tpu-v6e-slice",
                "cloud.google.com/gke-tpu-topology": "2x2",
            },
        )
        trainer = pod_spec["containers"][0]
        self.assertEqual(trainer["image"], SAMPLE_ENV["sft_tpu_torchtitan_image_url"])
        self.assertEqual(trainer["resources"]["limits"]["google.com/tpu"], "4")
        self.assertEqual(trainer["resources"]["limits"]["memory"], "128Gi")
        self._assert_gcsfuse_and_shm(pod_spec, "example-proj-trn-tt-sft-sh")
        self._assert_no_startup_installs(docs)

    def test_multi_host_jobset_overlay_invariants(self) -> None:
        docs = _kustomize_render(
            MANIFESTS_ROOT / "sft-tpu-torchtitan-multi-host",
            "v6e-4x4-gemma-4-12b-lora",
        )
        jobsets = [d for d in docs if d["kind"] == "JobSet"]
        self.assertEqual(len(jobsets), 1)
        jobset = jobsets[0]
        name = jobset["metadata"]["name"]
        self.assertEqual(name, "tt-sft-mh-v6e-4x4-gemma-4-12b")
        # JobSet pod names follow <jobset>-<replicated_job>-<jobIdx>-<podIdx>-<rand5>.
        replicated_job_name = jobset["spec"]["replicatedJobs"][0]["name"]
        max_pod_name = f"{name}-{replicated_job_name}-0-0-abcde"
        self.assertLessEqual(len(max_pod_name), 63, max_pod_name)

        replicated_job_spec = jobset["spec"]["replicatedJobs"][0]["template"]["spec"]
        self.assertEqual(replicated_job_spec["completions"], 4)
        self.assertEqual(replicated_job_spec["parallelism"], 4)
        pod_spec = replicated_job_spec["template"]["spec"]
        self.assertTrue(pod_spec["hostNetwork"])
        self.assertEqual(
            pod_spec["nodeSelector"],
            {
                "cloud.google.com/compute-class": "tpu-v6e-4x4",
                "cloud.google.com/gke-tpu-accelerator": "tpu-v6e-slice",
                "cloud.google.com/gke-tpu-topology": "4x4",
            },
        )
        trainer = pod_spec["containers"][0]
        self.assertEqual(trainer["image"], SAMPLE_ENV["sft_tpu_torchtitan_image_url"])
        # Verify ConfigMap nameSuffix propagated into JobSet envFrom and volumes.
        cm_names = {d["metadata"]["name"] for d in docs if d["kind"] == "ConfigMap"}
        self.assertIn(trainer["envFrom"][0]["configMapRef"]["name"], cm_names)
        script_vol = next(
            v for v in pod_spec["volumes"] if v["name"] == "train-script-vol"
        )
        self.assertIn(script_vol["configMap"]["name"], cm_names)
        self._assert_gcsfuse_and_shm(pod_spec, "example-proj-trn-tt-sft-mh")
        self._assert_no_startup_installs(docs)
        train_cm = next(
            d
            for d in docs
            if d["kind"] == "ConfigMap"
            and d["metadata"]["name"].startswith("train-script")
        )
        train_sh = train_cm["data"]["train.sh"]
        self.assertIn('HF_HOME="/tmp/hf-cache"', train_sh)
        self.assertIn("--rdzv_backend=static", train_sh)

    def test_documentation_paths_and_resource_names_resolve(self) -> None:
        for guide_dir, expected_res in (
            ("sft-tpu-torchtitan-single-host", "job/tt-sft-sh-v6e-2x2-gemma-4-12b"),
            ("sft-tpu-torchtitan-multi-host", "jobset/tt-sft-mh-v6e-4x4-gemma-4-12b"),
        ):
            readme = (DOCS_ROOT / guide_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn(expected_res, readme)
            for rel in re.findall(r"\$\{ACP_REPO_DIR\}/([A-Za-z0-9_./-]+)", readme):
                target = REPO_ROOT / rel
                self.assertTrue(
                    target.exists(), f"Missing path in {guide_dir}/README.md: {rel}"
                )
            for link in re.findall(r"\]\((/[A-Za-z0-9_./-]+)\)", readme):
                target = REPO_ROOT / link.lstrip("/")
                self.assertTrue(
                    target.exists(), f"Broken link in {guide_dir}/README.md: {link}"
                )

    def _assert_gcsfuse_and_shm(
        self, pod_spec: dict[str, Any], expected_bucket: str
    ) -> None:
        dshm = next(v for v in pod_spec["volumes"] if v["name"] == "dshm")
        self.assertEqual(dshm["emptyDir"]["sizeLimit"], "32Gi")
        gcs = next(v for v in pod_spec["volumes"] if v["name"] == "gcs-output")
        attrs = gcs["csi"]["volumeAttributes"]
        self.assertEqual(attrs["bucketName"], expected_bucket)
        self.assertEqual(attrs["hostNetworkPodKSA"], "true")
        self.assertNotIn("hostNetworkPodKSA", attrs["mountOptions"])
        self.assertIn("metadata-cache:ttl-secs:0", attrs["mountOptions"])

    def _assert_no_startup_installs(self, docs: list[dict[str, Any]]) -> None:
        raw = yaml.safe_dump_all(docs)
        self.assertNotIn("pip install", raw)
        self.assertNotIn("pip3 install", raw)
        self.assertNotIn("apt-get install", raw)


if __name__ == "__main__":
    unittest.main()
