# Development Tools

## Tools

### `.gitignore`

- A `.gitignore` file to exclude files that usually should not be committed
  while doing development work.

### `bin`

#### `cleanup_terraform.sh`

- Removes any `.terraform` directories in the repository.
- Lists any`terraform.tfstate` files that exist.

#### `configure_development.sh`

- Used `git update-index --assume-unchanged` on a list of files that usually
  should not be committed while doing development work.
- Applies a development `.gitignore` file to exclude additional files that
  usually should not be committed while doing development work.

#### `dictionaries_check.sh`

- Checks that the CSpell dictionary files are:
  - All lowercase
  - Sorted
  - Unique

#### `dictionaries_fix.sh`

- Fixes the CSpell dictionary files so that they are:
  - All lowercase
  - Sorted
  - Unique

#### `unconfigure_development.sh`

- Used `git update-index ---no-assume-unchanged` on a list of files so they show
  up in `git status` again.
- Removes the development `.gitignore` file.

#### `update_tag_hf-model-vllm-gpu-tutorial.sh`

- Updates the `hf-model-vllm-gpu-tutorial` on the remote repo with the current
  commit from your local repo.

#### `update_tag_hf-model-vllm-tpu-tutorial`

- Updates the `hf-model-vllm-tpu-tutorial` on the remote repo with the current
  commit from your local repo.

#### `update_terraform_lock_files`

- Searches for `version.tf` in the configured `search_directories`.
- Display the current Terraform providers and versions in all the `version.tf`
  files.
- Updates the `.terraform.lock.hcl` for all of the `version.tf` files and stages
  them for commit.

### `bin\helpers`

#### `git.sh`

- Contains variables and configuration used by some of the scripts.
