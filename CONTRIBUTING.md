# How to contribute

We'd love to accept your patches and contributions to this project.

## Before you begin

### Sign our Contributor License Agreement

Contributions to this project must be accompanied by a
[Contributor License Agreement](https://cla.developers.google.com/about) (CLA).
You (or your employer) retain the copyright to your contribution; this simply
gives us permission to use and redistribute your contributions as part of the
project.

If you or your current employer have already signed the Google CLA (even if it
was for a different project), you probably don't need to do it again.

Visit <https://cla.developers.google.com/> to see your current agreements or to
sign a new one.

### Review our community guidelines

This project follows
[Google's Open Source Community Guidelines](https://opensource.google/conduct/).

## Contribution process

### Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://help.github.com/articles/about-pull-requests/) for more
information on using pull requests.

### Coding style and formatting

#### Python

The repository requires that Python files:

- Use the [Black](https://github.com/psf/black) code formatter and style.
- Use the [isort](https://github.com/PyCQA/isort) to organize imports.

#### Markdown

The repository requires that files use the
[Prettier](https://github.com/prettier/prettier) code formatter and style. For
more information about Prettier's configuration for this project, see
[the Prettier configuration file](/.prettierrc)

#### Terraform

We follow the guidelines and recommendations in the
[Google Cloud Best practices for using Terraform](https://cloud.google.com/docs/terraform/best-practices-for-terraform)
document, unless noted otherwise.

The repository requires that files use built-in formatting using the
`terraform fmt` command.

## Development environment

### Requirements

To setup a development environment you need:

- A POSIX-compliant shell
- An OCI-compatible container runtime. Tested with Docker for Linux 20.10.21
- An IDE or text editor

> A Visual Studio Code dev container is included in the repository.
>
> The Visual Studio Code Dev Containers extension is only available for
> Microsoft Visual Studio Code in the Visual Studio Code Marketplace. Currently
> the extension is not available for Code - OSS in the Open VSX Registry.
>
> Recommended extensions and configuration are listed in the
> [Code OSS](#code-oss) section below.

### Dev container configuration

To set up a development environment, we designed a
[Visual Studio Code Dev Container](https://code.visualstudio.com/docs/devcontainers/containers)
that includes all the necessary tooling and Visual Studio Code (VS Code)
extensions that you need to work on this project. We use this dev container to
build the project from both VS Code and the command-line.

To inspect the development environment container image configuration and build
descriptors, refer to the contents of the `.devcontainer` directory:

- [.devcontainer/devcontainer.json](/.devcontainer/devcontainer.json):
  development container creation and access directives
  ([reference](https://code.visualstudio.com/docs/remote/devcontainerjson-reference)).
- [.devcontainer/Dockerfile](/.devcontainer/Dockerfile): dev container image
  build descriptor
  ([reference](https://docs.docker.com/engine/reference/builder/)).

For more information about creating containerized development environments,
refer to
[Create a development container](https://code.visualstudio.com/docs/remote/create-dev-container).

### Develop inside a container running on a remote host

If you don't have a container runtime engine on your local host, but you have
one available on a remote host, you can connect to the remote host and use that
container runtime. For more information, refer to
[Develop on a remote Docker host](https://code.visualstudio.com/remote/advancedcontainers/develop-remote-host).

### Code OSS

For Visual Studio Code - Open Source ("Code - OSS"), the following extensions
from the Open VSX Registry are recommend:

- Black Formatter (`ms-python.black-formatter`)
- Code Spell Checker (`streetsidesoftware.code-spell-checker`)
- EditorConfig for VS Code (`editorconfig.editorconfig`)
- HashiCorp Terraform (`hashicorp.terraform`)
- isort (`ms-python.isort`)
- Prettier - Code formatter (`esbenp.prettier-vscode`)

The settings in the [devcontainer.json](/.devcontainer/devcontainer.json#L9) are
also recommended.
