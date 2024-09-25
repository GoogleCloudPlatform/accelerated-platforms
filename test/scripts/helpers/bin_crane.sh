#!/usr/bin/env bash

# Copyright 2024 Google LLC
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

BIN_DIRECTORY=${BIN_DIRECTORY:-${HOME}/bin}

echo_title "Checking for crane"

print_and_execute_no_check "crane version"
exit_code=${?}

case ${exit_code} in
0)
    echo_success "crane found"
    ;;
127)
    echo_warning "crane not found, installing crane..."

    if go version; then
        echo_title "Installing crane via go"
        print_and_execute "go install github.com/google/go-containerregistry/cmd/crane@latest && \
        crane version"
    else
        VERSION="v0.20.2"
        OS="Linux"
        ARCH="x86_64"

        echo_title "Installing crane ${VERSION} for ${OS}-${ARCH} to ${BIN_DIRECTORY}"

        print_and_execute "mkdir -p ${BIN_DIRECTORY}
        cd ${BIN_DIRECTORY} && \
        curl -sL https://github.com/google/go-containerregistry/releases/download/${VERSION}/go-containerregistry_${OS}_${ARCH}.tar.gz > go-containerregistry.tar.gz && \
        tar -zxvf go-containerregistry.tar.gz crane && \
        rm -f go-containerregistry.tar.gz && \
        crane version"
    fi
    ;;
*)
    echo_error "Unhandled exit code ${exit_code}"
    ;;
esac
