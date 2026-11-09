# GKE Base Platform reference implementation

## Pull the source code

- Open [Cloud Shell](https://cloud.google.com/shell).

- Clone the repository and set the repository directory environment variable.

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

## Configure the platform

Terraform loads variables in the following order, with later sources taking
precedence over earlier ones:

- Environment variables (`TF_VAR_<variable_name>`)
- Any `*.auto.tfvars` or files, processed in lexical order of their filenames.
- Any `-var` and `-var-file` options on the command line, in the order they are
  provided.

For more information about providing values for Terraform input variables, see
[Terraform input variables](https://developer.hashicorp.com/terraform/language/values/variables).

- Set the platform default project ID

  ```shell
  export TF_VAR_platform_default_project_id="<PROJECT_ID>"
  ```

  **-- OR --**

  ```shell
  vi ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars
  ```

  ```hcl
  platform_default_project_id = "<PROJECT_ID>"
  ```

## Install Terraform 1.8.0+

> [!IMPORTANT]  
> At the time this guide was written, Cloud Shell had Terraform v1.5.7 installed
> by default. Terraform version 1.8.0 or later is required for this guide.

- Run the `install_terraform.sh` script to install Terraform 1.8.0.

  ```shell
  "${ACP_REPO_DIR}/tools/bin/install_terraform.sh"
  ```

## Deploy

- Deploy the reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/deploy-ap.sh
  ```

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/deploy-standard.sh
  ```

## Next steps: Deploy a workload use case

Once the GKE Base Platform core infrastructure is provisioned (or using each use
case's one-command deployment script, which automatically runs
`core/deploy-standard.sh` or `core/deploy-ap.sh`), you can deploy any of the
following workload reference implementations:

- **Secure Runtimes for AI Agents (GKE Agent Sandbox & Agent Substrate)**:
  - [Secure runtimes for AI agents reference architecture (gVisor sandboxing, zero-secret egress, and millisecond memory snapshot restore)](/docs/platforms/gke/base/use-cases/agent-substrate-security-demo/README.md)
  - [Secure runtimes for AI agents reference implementation & 4-Act Red Team vs. Blue Team demo](/platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/README.md)
- **AI Inference & Generative Media**:
  - [Inference reference implementation (GPUs & TPUs)](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  - [ComfyUI reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/examples/comfyui/README.md)
- **Model Training & Fine-Tuning**:
  - [Training reference architecture](/docs/platforms/gke/base/use-cases/training-ref-arch/README.md)
- **Reinforcement Learning (RLHF / GRPO)**:
  - [Reinforcement learning reference implementation](/platforms/gke/base/use-cases/reinforcement-learning/terraform/README.md)
- **Federated Learning**:
  - [Federated learning reference architecture](/docs/platforms/gke/base/use-cases/federated-learning/README.md)

## Teardown

- Teardown the reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/teardown-ap.sh
  ```

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/teardown-standard.sh
  ```
