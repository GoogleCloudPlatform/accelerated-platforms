# accelerated-platforms CI/CD Terraform

This folder contains the IaC for the CI/CD environment of this repository.

## Initial Setup

- Configure the environment.

  ```
  vi _shared_config/build.auto.tfvars
  ```

  ```
  build_project_id = "accelerated-platforms"
  build_location   = "us-central1"
  ```

- Initialize the environment.

  ```
  cd initialize && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan && \
  terraform init -force-copy -migrate-state && \
  rm terraform.tfstate terraform.tfstate.backup && \
  cd ..
  ```

- Create a GitHub personal access token (classic) with the following
  permissions:

  | Scope       |
  | ----------- |
  | repo        |
  | read:user   |
  | read:org    |
  | delete_repo |

- Add the GitHub token as a new version to the `github-token` secret.

- Apply Terraform

  ```
  ./apply.sh
  ```

- Commit changes to repository

  ```
  git add . && \
  git commit -m "Configure and initialize ci-cd environment" && \
  git push
  ```

Subsequent change will be applied by the trigger when the changes are pushed to
the `main` branch.
