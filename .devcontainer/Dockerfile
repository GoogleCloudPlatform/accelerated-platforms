FROM hashicorp/terraform:1.5.7 AS terraform
FROM koalaman/shellcheck:v0.10.0 AS shellcheck
FROM mvdan/shfmt:v3.10.0 AS shfmt

FROM python:3.13-bookworm AS python-builder

SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

RUN mkdir -p /venv

COPY dependencies/requirements.txt /venv/requirements.txt

RUN python -m venv /venv \
  && . /venv/bin/activate \
  && pip install -r /venv/requirements.txt

FROM node:23.3-bookworm AS npm-builder

SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

COPY dependencies/package.json dependencies/package-lock.json /
RUN npm audit \
  && npm install --strict-peer-deps \
  && npm cache clean --force

FROM python:3.13-bookworm AS devcontainer

SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

COPY --from=shellcheck /bin/shellcheck /usr/bin/
COPY --from=shfmt /bin/shfmt /usr/bin/
COPY --from=terraform /bin/terraform /usr/bin/
COPY --from=python-builder /venv /venv
COPY --from=npm-builder /node_modules /node_modules

ENV PATH="${PATH}:/venv/bin"
ENV PATH="${PATH}:/node_modules/.bin"

# Quick smoke test
RUN \
  shellcheck --version \
  && shfmt --version \
  && CHECKPOINT_DISABLE="not needed for version checks" terraform --version
