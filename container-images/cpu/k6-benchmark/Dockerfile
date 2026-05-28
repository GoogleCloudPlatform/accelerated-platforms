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

FROM grafana/k6:1.7.1

USER root

WORKDIR /app
# Create the /output directory and ensure k6 owns it, along with /app
RUN mkdir -p /output && chown -R k6:k6 /app /output

COPY --chown=k6:k6 scripts /app/scripts
COPY --chmod=a+x --chown=k6:k6 entrypoint.sh /app/entrypoint.sh

# Switch back to the unprivileged k6 user
USER k6

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["--help"]
