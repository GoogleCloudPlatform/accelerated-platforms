#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for capture_vllm_config.py."""

import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture_vllm_config as cvc


class CaptureVllmConfigTest(unittest.TestCase):
    """Tests for vLLM configuration capture helpers."""

    def test_normalize_cli_args_multiline_shell_script(self):
        script = (
            "set -e\n"
            "vllm serve \\\n"
            "  $(MODEL_ID) \\\n"
            "  # inline comment line\n"
            "  --port 8080 \\\n"
            "  --tensor-parallel-size=$(TENSOR_PARALLEL_SIZE) \\\n"
            '  --kv-transfer-config \'{"kv_connector":"TPUConnector","kv_role":"kv_producer"}\'\n'
            "echo done\n"
        )
        tokens = cvc.normalize_cli_args([script], ["/bin/sh", "-c"])
        self.assertEqual(
            tokens,
            [
                "$(MODEL_ID)",
                "--port",
                "8080",
                "--tensor-parallel-size=$(TENSOR_PARALLEL_SIZE)",
                "--kv-transfer-config",
                '{"kv_connector":"TPUConnector","kv_role":"kv_producer"}',
            ],
        )

    def test_parse_kv_transfer_and_vllm_args(self):
        args = [
            "Qwen/Qwen3-32B",
            "--port",
            "8080",
            "--tensor-parallel-size=8",
            "--disable-uvicorn-access-log",
            "--kv-transfer-config",
            '{"kv_connector":"TPUConnector","kv_connector_module_path":"vllm_tpu.distributed.tpu_connector","kv_role":"kv_both"}',
        ]
        kv = cvc.parse_kv_transfer(args)
        self.assertTrue(kv["enabled"])
        self.assertEqual(kv["kv_connector"], "TPUConnector")
        self.assertEqual(kv["kv_role"], "kv_both")
        self.assertEqual(
            kv["kv_connector_module_path"],
            "vllm_tpu.distributed.tpu_connector",
        )

        params = cvc.parse_vllm_args(args)
        self.assertEqual(params["port"], "8080")
        self.assertEqual(params["tensor_parallel_size"], "8")
        self.assertTrue(params["disable_uvicorn_access_log"])
        self.assertNotIn("kv_transfer_config", params)

    def test_expand_disaggregated_sets_does_not_mutate_input(self):
        dset = {
            "apiVersion": "disaggregatedset.sigs.k8s.io/v1alpha1",
            "kind": "DisaggregatedSet",
            "metadata": {"name": "llm-d-model-server", "namespace": "llmd"},
            "spec": {
                "roles": [
                    {
                        "name": "prefill",
                        "spec": {
                            "replicas": 2,
                            "leaderWorkerTemplate": {
                                "workerTemplate": {
                                    "metadata": {
                                        "labels": {
                                            "llm-d.ai/guide": "pd-disaggregation"
                                        }
                                    },
                                    "spec": {
                                        "containers": [
                                            {
                                                "name": "modelserver",
                                                "image": "vllm/vllm-tpu:v1",
                                            }
                                        ]
                                    },
                                }
                            },
                        },
                    },
                    {
                        "name": "decode",
                        "spec": {"replicas": 1},
                    },
                ]
            },
        }
        original = copy.deepcopy(dset)
        expanded = cvc.expand_disaggregated_sets([dset])
        self.assertEqual(dset, original)
        self.assertEqual(len(expanded), 2)
        self.assertEqual(expanded[0]["metadata"]["name"], "llm-d-model-server-prefill")
        self.assertEqual(
            cvc.deep_get(
                expanded[0],
                [
                    "spec",
                    "leaderWorkerTemplate",
                    "workerTemplate",
                    "metadata",
                    "labels",
                    cvc.ROLE_LABEL,
                ],
            ),
            "prefill",
        )
        self.assertEqual(
            cvc.deep_get(
                expanded[1],
                [
                    "spec",
                    "leaderWorkerTemplate",
                    "workerTemplate",
                    "metadata",
                    "labels",
                    cvc.ROLE_LABEL,
                ],
            ),
            "decode",
        )

    @mock.patch.object(cvc, "run_kubectl")
    def test_get_live_pods_leaderworkerset_selector(self, mock_kubectl):
        mock_kubectl.return_value = {
            "items": [
                {
                    "metadata": {"name": "lws-prefill-0"},
                    "spec": {"nodeName": "node-1"},
                    "status": {
                        "phase": "Running",
                        "podIP": "10.0.0.2",
                        "startTime": "2026-01-01T00:00:00Z",
                        "containerStatuses": [
                            {
                                "name": "modelserver",
                                "image": "vllm/vllm-tpu:v1",
                                "imageID": "sha256:abc",
                                "ready": True,
                                "restartCount": 0,
                                "state": {"running": {}},
                            }
                        ],
                    },
                }
            ]
        }
        workload = {
            "kind": "LeaderWorkerSet",
            "metadata": {"name": "llm-d-model-server-prefill"},
            "spec": {},
        }
        pods = cvc.get_live_pods("llmd", workload)
        self.assertEqual(len(pods), 1)
        mock_kubectl.assert_called_once_with(
            [
                "get",
                "pods",
                "-n",
                "llmd",
                "-l",
                "leaderworkerset.sigs.k8s.io/name=llm-d-model-server-prefill",
                "-o",
                "json",
            ]
        )
        scale = cvc.scaling_state(workload, [], pods)
        self.assertEqual(scale["ready_replicas"], 1)

    def test_build_env_map_substitutes_previously_defined_vars(self):
        container = {
            "env": [
                {
                    "name": "POD_IP",
                    "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}},
                },
                {
                    "name": "VLLM_HOST_IP",
                    "value": "$(POD_IP)",
                },
            ]
        }
        env_map = cvc.build_env_map(container, {})
        self.assertEqual(env_map["POD_IP"], "<fieldRef:status.podIP>")
        self.assertEqual(env_map["VLLM_HOST_IP"], "<fieldRef:status.podIP>")

    @mock.patch.object(cvc, "get_live_pods", return_value=[])
    @mock.patch.object(cvc, "run_kubectl")
    def test_capture_deduplicates_lws_owned_child_deployments(
        self, mock_kubectl, _mock_pods
    ):
        import tempfile

        child_deploy = {
            "kind": "Deployment",
            "metadata": {
                "name": "pd-disagg-decode",
                "ownerReferences": [
                    {"kind": "LeaderWorkerSet", "name": "pd-disagg-decode"}
                ],
            },
            "spec": {
                "replicas": 1,
                "template": {
                    "metadata": {"labels": {cvc.ROLE_LABEL: "decode"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "modelserver",
                                "image": "vllm/vllm-torchtpu:v0.29.0",
                            }
                        ]
                    },
                },
            },
        }
        parent_lws = {
            "kind": "LeaderWorkerSet",
            "metadata": {"name": "pd-disagg-decode"},
            "spec": {
                "replicas": 1,
                "leaderWorkerTemplate": {
                    "workerTemplate": {
                        "metadata": {"labels": {cvc.ROLE_LABEL: "decode"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "modelserver",
                                    "image": "vllm/vllm-torchtpu:v0.29.0",
                                }
                            ]
                        },
                    }
                },
            },
        }
        mock_kubectl.side_effect = [
            {"items": [child_deploy]},
            {"items": [parent_lws]},
        ]
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            res = cvc.capture_vllm_config("llmd", "pd-disaggregation", tmp.name)
        self.assertEqual(res["detected_architecture"]["model_server_count"], 1)
        self.assertEqual(res["model_servers"][0]["workload_kind"], "LeaderWorkerSet")


if __name__ == "__main__":
    unittest.main()
