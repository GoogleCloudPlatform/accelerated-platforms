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

FROM nvcr.io/nvidia/ai-dynamo/tensorrtllm-runtime:1.6.1@sha256:597d7606c515e7f8ba6a4e0e94d84a26cf1c2c5966d07696b5dbab08e4540f41

USER 0

# Workaround for https://github.com/ai-dynamo/dynamo/issues/16690: the base
# image's NIXL_PLUGIN_DIR holds the NIXL plugins bundled with TensorRT-LLM, which
# lack the libplugin_POSIX.so that KVBM initializes at startup. Merge them with
# libplugin_POSIX.so from the nixl-cu13 wheel, keeping the TensorRT-LLM UCX
# plugin so that a single UCX build is loaded. The plugin finds its vendored
# liburing and libaio through RUNPATH $ORIGIN/.., which resolves relative to the
# symlink, so append the nixl-cu13 library directory, which only holds
# hash-suffixed libraries, to LD_LIBRARY_PATH. Remove once the base image's
# NIXL_PLUGIN_DIR includes libplugin_POSIX.so, as proposed in
# https://github.com/ai-dynamo/dynamo/pull/17227, or together with the
# kvbm-offloading mode, because https://github.com/ai-dynamo/dynamo/pull/17229
# proposes removing KVBM from the TensorRT-LLM backend.
RUN set -eux; \
    test -f "${NIXL_PLUGIN_DIR}/libplugin_UCX.so"; \
    if [ -e "${NIXL_PLUGIN_DIR}/libplugin_POSIX.so" ]; then \
      echo "The base image ships ${NIXL_PLUGIN_DIR}/libplugin_POSIX.so; remove this workaround." >&2; \
      exit 1; \
    fi; \
    mkdir /opt/nixl-plugins; \
    ln -s "${NIXL_PLUGIN_DIR}"/* /opt/nixl-plugins/; \
    ln -s /opt/dynamo/venv/lib/python3.12/site-packages/nixl_cu13.libs/nixl/libplugin_POSIX.so /opt/nixl-plugins/

ENV NIXL_PLUGIN_DIR=/opt/nixl-plugins \
    LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/opt/dynamo/venv/lib/python3.12/site-packages/nixl_cu13.libs

# The base image's dynamo user, as numeric IDs so that Kubernetes can verify
# runAsNonRoot.
USER 1000:0

# Fail the build, instead of the Pods on the GPU nodes, if a new base image
# breaks what the Kubernetes manifests rely on:
# - GKE mounts the NVIDIA driver libraries in /usr/local/nvidia/lib64 when the
#   container starts, after ldconfig ran at build time, so the dynamic loader
#   finds them only through LD_LIBRARY_PATH.
# - The merged POSIX plugin loads with the environment above.
# - The kvbm package, which `--connector kvbm` loads, matches the Dynamo runtime
#   and imports as the user that the Pods run as.
RUN case ":${LD_LIBRARY_PATH}:" in \
      *:/usr/local/nvidia/lib64:*) ;; \
      *) echo "LD_LIBRARY_PATH doesn't include /usr/local/nvidia/lib64: ${LD_LIBRARY_PATH}" >&2; exit 1 ;; \
    esac \
    && python3 -c 'import ctypes, os; ctypes.CDLL(os.environ["NIXL_PLUGIN_DIR"] + "/libplugin_POSIX.so")' \
    && python3 -c 'import importlib.metadata as md; assert md.version("kvbm") == md.version("ai-dynamo-runtime")' \
    && python3 -c 'import os, kvbm; assert os.path.isdir(os.path.join(os.path.dirname(kvbm.__file__), "trtllm_integration", "connector"))'
