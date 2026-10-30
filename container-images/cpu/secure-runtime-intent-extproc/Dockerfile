# syntax=docker.io/docker/dockerfile:1.17.1

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

FROM golang:1.25-bookworm AS builder

WORKDIR /src
COPY --from=primary go.mod go.sum ./
RUN go mod download
COPY --from=primary *.go ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/intent-extproc .

FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /out/intent-extproc /intent-extproc

USER 65532:65532
EXPOSE 50051 8080

ENTRYPOINT ["/intent-extproc"]
