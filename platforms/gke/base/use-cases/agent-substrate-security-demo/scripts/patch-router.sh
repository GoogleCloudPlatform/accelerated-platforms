#!/usr/bin/env bash
# Copyright 2026 Google LLC
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

# Configures atenet-router with a 60s parked-request budget and an HTTP/1.1 + h2c bridge on :8080 (Service port 80).

set -euo pipefail

kubectl apply -f - >/dev/null <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: atenet-router-envoy-config
  namespace: ate-system
data:
  envoy.yaml: |
    admin:
      address:
        socket_address:
          address: 127.0.0.1
          port_value: 9901

    node:
      id: substrate-envoy-node
      cluster: substrate-router-cluster

    bootstrap_extensions:
    - name: envoy.bootstrap.internal_listener
      typed_config:
        "@type": type.googleapis.com/envoy.extensions.bootstrap.internal_listener.v3.InternalListener

    dynamic_resources:
      lds_config:
        resource_api_version: V3
        ads: {}
      cds_config:
        resource_api_version: V3
        ads: {}
      ads_config:
        api_type: DELTA_GRPC
        transport_api_version: V3
        grpc_services:
        - envoy_grpc:
            cluster_name: xds_cluster

    static_resources:
      listeners:
      - name: envoy_metrics
        stat_prefix: admin_metrics
        address:
          socket_address:
            address: "::"
            ipv4_compat: true
            port_value: 9902
        filter_chains:
        - filters:
          - name: envoy.filters.network.http_connection_manager
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
              stat_prefix: admin_metrics
              route_config:
                name: envoy_metrics
                virtual_hosts:
                - name: envoy_metrics
                  domains: ["*"]
                  routes:
                  - match:
                      path: /stats/prometheus
                      headers:
                      - name: ":method"
                        string_match: { exact: GET }
                    route: { cluster: envoy_admin }
                  - match:
                      path: /ready
                      headers:
                      - name: ":method"
                        string_match: { exact: GET }
                    route: { cluster: envoy_admin }
              http_filters:
              - name: envoy.filters.http.router
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
      - name: ingress_http_bridge
        stat_prefix: ingress_http_bridge
        address:
          socket_address:
            address: "::"
            ipv4_compat: true
            port_value: 8080
        filter_chains:
        - filters:
          - name: envoy.filters.network.http_connection_manager
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
              stat_prefix: ingress_http_bridge
              codec_type: AUTO
              http2_protocol_options: {}
              route_config:
                name: ingress_http_bridge_route
                virtual_hosts:
                - name: ingress_http_bridge_vhost
                  domains: ["*"]
                  routes:
                  - match:
                      prefix: "/"
                    route:
                      cluster: ingress_https_loopback
                      timeout: 300s
              http_filters:
              - name: envoy.filters.http.router
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
      clusters:
      - name: envoy_admin
        connect_timeout: 0.25s
        type: STATIC
        load_assignment:
          cluster_name: envoy_admin
          endpoints:
          - lb_endpoints:
            - endpoint:
                address:
                  socket_address:
                    address: 127.0.0.1
                    port_value: 9901
      - name: xds_cluster
        connect_timeout: 0.25s
        type: STRICT_DNS
        lb_policy: ROUND_ROBIN
        typed_extension_protocol_options:
          envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
            "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
            explicit_http_config:
              http2_protocol_options: {}
        load_assignment:
          cluster_name: xds_cluster
          endpoints:
          - lb_endpoints:
            - endpoint:
                address:
                  socket_address:
                    address: 127.0.0.1
                    port_value: 18000
      - name: ingress_https_loopback
        connect_timeout: 5s
        type: STATIC
        typed_extension_protocol_options:
          envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
            "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
            explicit_http_config:
              http2_protocol_options: {}
        transport_socket:
          name: envoy.transport_sockets.tls
          typed_config:
            "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
            sni: atenet-router.ate-system.svc
            common_tls_context:
              alpn_protocols: ["h2"]
              tls_certificates:
              - certificate_chain:
                  filename: /run/podidentity.podcert.ate.dev/credential-bundle.pem
                private_key:
                  filename: /run/podidentity.podcert.ate.dev/credential-bundle.pem
                watched_directory:
                  path: /run/podidentity.podcert.ate.dev
        load_assignment:
          cluster_name: ingress_https_loopback
          endpoints:
          - lb_endpoints:
            - endpoint:
                address:
                  socket_address:
                    address: 127.0.0.1
                    port_value: 8443
EOF

args="$(kubectl -n ate-system get deploy atenet-router -o jsonpath='{.spec.template.spec.containers[0].args}')"
if [[ "${args}" != *"--parked-request-budget="* ]]; then
  kubectl -n ate-system patch deploy atenet-router --type=json \
    -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--parked-request-budget=60s"}]' >/dev/null
fi
envoy_ports="$(kubectl -n ate-system get deploy atenet-router -o jsonpath='{.spec.template.spec.containers[1].ports[*].name}')"
if [[ " ${envoy_ports} " != *" http "* ]]; then
  kubectl -n ate-system patch deploy atenet-router --type=json \
    -p '[{"op":"add","path":"/spec/template/spec/containers/1/ports/-","value":{"name":"http","containerPort":8080,"protocol":"TCP"}}]' >/dev/null
fi
svc_ports="$(kubectl -n ate-system get svc atenet-router -o jsonpath='{.spec.ports[*].name}')"
if [[ " ${svc_ports} " != *" http "* ]]; then
  kubectl -n ate-system patch svc atenet-router --type=json \
    -p '[{"op":"add","path":"/spec/ports/-","value":{"name":"http","port":80,"targetPort":8080,"protocol":"TCP"}}]' >/dev/null
fi
if kubectl -n ate-system get networkpolicy atenet-router >/dev/null 2>&1; then
  np_ports="$(kubectl -n ate-system get networkpolicy atenet-router -o jsonpath='{.spec.ingress[0].ports[*].port}')"
  if [[ " ${np_ports} " != *" http "* ]]; then
    kubectl -n ate-system patch networkpolicy atenet-router --type=json \
      -p '[{"op":"add","path":"/spec/ingress/0/ports/-","value":{"protocol":"TCP","port":"http"}}]' >/dev/null
  fi
fi
grace="$(kubectl -n ate-system get deploy atenet-router -o jsonpath='{.spec.template.spec.terminationGracePeriodSeconds}')"
if [[ "${grace:-0}" -lt 120 ]]; then
  kubectl -n ate-system patch deploy atenet-router --type=merge \
    -p '{"spec":{"template":{"spec":{"terminationGracePeriodSeconds":120}}}}' >/dev/null
fi
kubectl -n ate-system rollout status deploy/atenet-router --timeout=5m >/dev/null
