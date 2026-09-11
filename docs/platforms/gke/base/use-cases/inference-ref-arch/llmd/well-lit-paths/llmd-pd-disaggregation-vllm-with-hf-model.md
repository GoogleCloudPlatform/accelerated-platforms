# Prefill/Decode Disaggregation

This guide implements llm-d prefill/decode disaggregation well-lit path on GKE
using
[Google Cloud Accelerated Platforms](https://github.com/GoogleCloudPlatform/accelerated-platforms).
To learn about prefill/decode disaggregation, refer to
[llm-d documentation](https://llm-d.ai/docs/well-lit-paths/foundations/pd-disaggregation).

## Prerequisite

This architecture and workflow assumes that the reader is familiar with the
following GKE, Google Cloud Networking and llm-d components:

- [Gateway API resources](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/gateway-api#gateway_resources)
- [GKE Gateway Controller](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/gateway-api#gateway_controller)
- [Google Cloud Load Balancer through GKE](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/service-load-balancer#load_balancer_types)
- [Gateway API Inference Extension(GAIE)](https://github.com/kubernetes-sigs/gateway-api-inference-extension/tree/main/docs/proposals/0683-epp-architecture-proposal)
- [vLLM-Optimized Inference Schedule](https://llm-d.ai/docs/architecture)
- [TPUs in GKE](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/tpus)

## Architecture

This guide is an implementation of
[llm-d prefill/decode disaggregation well-lit path](https://github.com/llm-d/llm-d/tree/main/guides/pd-disaggregation),
following the
[Google TPU variant](https://github.com/llm-d/llm-d/blob/main/guides/pd-disaggregation/README.tpu.md)
of that guide. In this guide, you will see how you can install llmd
prefill/decode disaggregation well-lit path on GKE using our
[GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md).
The
[well-lit](https://github.com/llm-d/llm-d/tree/main/guides/pd-disaggregation)
path provides you the instructions to create the prefill/decode disaggregation
related resources but you still need to figure out how to create your GKE
cluster and underlying infrastructure dependencies such as inference-gateway,
custom compute classes for obtaining accelerators, storage for model download
etc. This guide provides you the cohesive approach to build your infrastructure
and apply llm-d prefill/decode disaggregation layer on top of it.

Prefill/decode disaggregation splits inference across two specialized pools of
model servers. Prefill workers process the input prompt, which is compute-bound.
Decode workers generate the output tokens, which is latency- and
memory-bandwidth-bound. Separating them removes prefill interference from the
decode phase, which lowers inter-token latency and lets each pool be scaled
independently. Disaggregation is implemented in the llm-d Router, so it composes
with the prefix- and load-aware routing used by the other well-lit paths.

On TPU, the KV cache produced by a prefill worker is transferred to a decode
worker using the vLLM `TPUConnector` over a dedicated side channel. This guide
therefore creates two model server deployments rather than one:

| Deployment | vLLM `kv_role` | vLLM port |
| :--------: | :------------: | :-------: |
|  prefill   | `kv_producer`  |  `8000`   |
|   decode   |   `kv_both`    |  `8200`   |

A routing sidecar runs alongside the decode pod and coordinates the two phases
of each request.

> [!NOTE] Prefill/decode disaggregation is not a target for all workloads. It
> benefits medium-large models with longer input sequence lengths, for example
> 10k input and 1k output rather than 200 input and 200 output. For short,
> balanced sequences the
> [optimized baseline](./llmd-optimized-baseline-vllm-with-hf-model.md) is
> usually a better fit.

## Pull the source code

- Open [Cloud Shell](https://cloud.google.com/shell).

- Clone the repository and change directory to the guide directory

  ```
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms && \
  export ACP_REPO_DIR="$(pwd)"
  ```

  To set the `ACP_REPO_DIR` value for new shell instances, write the value to
  your shell initialization file.

  `bash`

  ```
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.bashrc
  ```

  `zsh`

  ```
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.zshrc
  ```

## Configure

Terraform loads variables in the following order, with later sources taking
precedence over earlier ones:

- Environment variables (`TF_VAR_<variable_name>`)
- Any `*.auto.tfvars` or files, processed in lexical order of their filenames.
- Any `-var` and `-var-file` options on the command line, in the order they are
  provided.

- Set the platform defaults project ID

  ```
  export TF_VAR_platform_default_project_id="<PROJECT_ID>"
  ```

  **-- OR --**

  ```
  platform_default_project_id="<PROJECT_ID>"
  sed -i '/^platform_default_project_id[[:blank:]]*=/{h;s/=.*/= "'"${platform_default_project_id}"'"/};${x;/^$/{s//platform_default_project_id = "'"${platform_default_project_id}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars
  ```

- Optional : By default, the platform name is set to `dev`. If you want to
  change it, set the platform name

  ```
  platform_name="<PLATFORM_NAME>"
  sed -i '/^platform_name[[:blank:]]*=/{h;s/=.*/= "'"${platform_name}"'"/};${x;/^$/{s//platform_name="'"${platform_name}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars
  ```

- Set the model to `qwen/qwen3-32b`, which is the default model for this
  deployment.

  ```
  llmd_model_id="qwen/qwen3-32b"
  sed -i "/^llmd_model_id[[:blank:]]*=/{h;s|=.*|= \"${llmd_model_id}\"|};\${x;/^$/{s|.*|llmd_model_id=\"${llmd_model_id}\"|;H};x}" "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/llmd-shared.auto.tfvars"
  ```

- In order to choose an accelerator and for the model you want to run, refer to
  the following table.

  |   Model   | GPU(h100) | GPU(h200) | GPU(RTX Pro 6000) | TPU(v6e) |
  | :-------: | :-------: | :-------: | :---------------: | :------: |
  | qwen3-32b |    ❌     |    ❌     |        ❌         |    ✅    |

- Run the following step to set the accelerator to `v6e`. The default
  accelerator for this deployment is `nvidia-rtx-pro`, which is not supported by
  this guide.

  ```
  llmd_accelerator_type="v6e"
  sed -i '/^llmd_accelerator_type[[:blank:]]*=/{h;s/=.*/= "'"${llmd_accelerator_type}"'"/};${x;/^$/{s//llmd_accelerator_type="'"${llmd_accelerator_type}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/llmd-shared.auto.tfvars
  ```

  Valid values for `ACCELERATOR` are:

  - `v6e` **(required)**

> [!IMPORTANT] The other llm-d well-lit paths in this repository run on a `2x2`
> (4 chip) TPU v6e slice. Prefill/decode disaggregation uses the `2x4` (8 chip)
> slice with `--tensor-parallel-size=8`, matching the upstream llm-d TPU guide.
> Because the prefill and decode pods each occupy a full slice, a single
> prefill/decode pair requires two `ct6e-standard-8t` nodes. Confirm your TPU
> quota before you deploy.

### Install Terraform 1.8.0+

> [!IMPORTANT]  
> At the time this guide was written, Cloud Shell had Terraform v1.5.7 installed
> by default. Terraform version 1.8.0 or later is required for this guide.

- Run the `install_terraform.sh` script to install Terraform 1.8.0.

  ```shell
  "${ACP_REPO_DIR}/tools/bin/install_terraform.sh"
  ```

## Deploy the entire stack except the model server

```
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/deploy-llmd-pd-disaggregation.sh
```

## Resources created

The `deploy-llmd-pd-disaggregation.sh` script will perform the following steps:

- Set up base GKE cluster platform and other infrastructure resources required
  for llm-d, including the `tpu-v6e-2x4` custom compute class.
- Create Gateway and Router for llm-d prefill/decode disaggregation. You will
  create model servers manually in the following sections of this guide.

## Download the model to Cloud Storage

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"
  ```

- [Generate a Hugging Face tokens](https://huggingface.co/docs/hub/security-tokens)
  with token type **Read**.
- Add the token to the secret manager

  ```
  HF_TOKEN_READ=<YOUR_HUGGINGFACE_READ_TOKEN>
  echo ${HF_TOKEN_READ} | gcloud secrets versions add ${huggingface_hub_access_token_read_secret_manager_secret_name} --data-file=- --project=${huggingface_secret_manager_project_id}
  ```

- Additionally, add the token to a secret named `HF_TOKEN` for the router.

  ```
  HF_TOKEN_READ=<YOUR_HUGGINGFACE_READ_TOKEN>
  kubectl -n ${llmd_namespace} create secret generic llm-d-hf-token --from-literal=HF_TOKEN="${HF_TOKEN_READ}"
  ```

- Configure the model download job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  ```

- Deploy the model download job.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Watch the model download job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-hf-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} logs job/${HF_MODEL_ID_HASH}-hf-model-to-gcs --all-containers --tail 10"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                       STATUS     COMPLETIONS   DURATION   AGE
  XXXXXXXX-hf-model-to-gcs   Complete   1/1           ###        ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Delete the model download job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

## Deploy the model server

- Configure the model server

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/llmd-pd-disaggregation/vllm/configure_vllm.sh"
  ```

- Deploy the model server

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/llmd-pd-disaggregation/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

  This creates both the prefill and the decode deployment.

  The Kubernetes manifests are based on the
  [Inference Quickstart recommendations](https://cloud.google.com/kubernetes-engine/docs/how-to/machine-learning/inference-quickstart).

- Watch the deployments until they are ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${llmd_namespace} get deployment/pd-disaggregation-tpu-vllm-prefill-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} deployment/pd-disaggregation-tpu-vllm-decode-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${llmd_namespace} logs deployment/pd-disaggregation-tpu-vllm-decode-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} --all-containers --tail 10"
  ```

  The first start is slow. Each pod is scheduled onto a newly auto-provisioned 8
  chip TPU node, streams the model from Cloud Storage, and then compiles the
  model for TPU.

## Verify llm-d deployment is up and running

- Set the environment variables

  ```
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"
  ```

- Get cluster credentials

  ```
  ${cluster_credentials_command}
  ```

- Check the all the deployments

  ```
  kubectl get deployments -n ${llmd_namespace}
  ```

  You should see three deployments similar to the following:

  ```
  NAME                                     READY   UP-TO-DATE   AVAILABLE   AGE
  pd-disaggregation-epp                    1/1     1            1           XX
  pd-disaggregation-tpu-vllm-decode-XXX    1/1     1            1           XX
  pd-disaggregation-tpu-vllm-prefill-XXX   1/1     1            1           XX
  ```

  Note:

  - pd-disaggregation-epp is the Gateway API Inference Extension endpoint
    picker, which makes the prefill and decode scheduling decisions.
  - pd-disaggregation-tpu-vllm-prefill-XXX and
    pd-disaggregation-tpu-vllm-decode-XXX are the model servers running
    inference of the model you chose. It may take some time for these
    deployments to be up completely depending upon the TPU availability

- Check all the resources

  ```
  kubectl get all -n ${llmd_namespace}
  ```

  You should see output similar to the following:

  ```
  NAME                                          READY   STATUS    RESTARTS   AGE
  pod/pd-disaggregation-epp-XXXX                1/1     Running   0          XX
  pod/pd-disaggregation-tpu-vllm-decode-XXXX    2/2     Running   0          XX
  pod/pd-disaggregation-tpu-vllm-prefill-XXXX   1/1     Running   0          XX

  NAME                                   TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                    AGE
  service/pd-disaggregation-epp          ClusterIP   XXXX         <none>        9002/TCP,9090/TCP,80/TCP   XX
  service/pd-disaggregation-ips-XXXX     ClusterIP   None         <none>        54321/TCP                  XX

  NAME                                                     READY   UP-TO-DATE   AVAILABLE   AGE
  deployment.apps/pd-disaggregation-epp                    1/1     1            1           XX
  deployment.apps/pd-disaggregation-tpu-vllm-decode-XXXX   1/1     1            1           XX
  deployment.apps/pd-disaggregation-tpu-vllm-prefill-XXXX  1/1     1            1           XX

  NAME                                                      DESIRED   CURRENT   READY   AGE
  replicaset.apps/pd-disaggregation-epp-XXXX                1         1         1       XX
  replicaset.apps/pd-disaggregation-tpu-vllm-decode-XXXX    1         1         1       XX
  replicaset.apps/pd-disaggregation-tpu-vllm-prefill-XXXX   1         1         1       XX
  ```

  The decode pod reports `2/2` containers because it runs the routing sidecar
  alongside the model server.

- Wait for the model server deployments to be ready before sending the request
  to them.

  ```
  watch --color --interval 5 --no-title   "kubectl --namespace=${llmd_namespace} get deployment.apps/pd-disaggregation-tpu-vllm-prefill-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} deployment.apps/pd-disaggregation-tpu-vllm-decode-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

- When the deployments are ready, you will output similar to the following

  ```
  NAME                                      READY   UP-TO-DATE   AVAILABLE   AGE
  pd-disaggregation-tpu-vllm-prefill-XXXX   1/1     1            1           XX
  pd-disaggregation-tpu-vllm-decode-XXXX    1/1     1            1           XX
  ```

## Send Test Requests

- Open [Cloud Shell](https://cloud.google.com/shell).
- Find the IP address of Gateway
  ```sh
  export IP=$(kubectl get gateway llm-d-inference-gateway -n ${llmd_namespace} -o jsonpath='{.status.addresses[0].value}')
  ```
- Open a temporary interactive shell inside the cluster:

  ```sh
  kubectl run curl-debug --rm -it \
      --image=cfmanteiga/alpine-bash-curl-jq \
      --env="IP=$IP" \
      --env="NAMESPACE=$llmd_namespace" \
      -- /bin/bash
  ```

- Send a completion request:

```sh
  curl -X POST http://${IP}/v1/completions \
      -H 'Content-Type: application/json' \
      -d '{
          "model": "qwen/qwen3-32b",
          "prompt": "How are you today?"
      }' | jq
```

- To confirm the request traversed the disaggregated path, check both model
  servers. The prefill server logs the prompt pass and the decode server logs
  the generation.

  ```sh
  kubectl --namespace=${llmd_namespace} logs -l llm-d.ai/role=prefill -c modelserver --tail 20
  kubectl --namespace=${llmd_namespace} logs -l llm-d.ai/role=decode -c modelserver --tail 20
  ```

## Teardown

Teardown the llm-d platform

```shell
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/teardown-llmd-pd-disaggregation.sh
```
