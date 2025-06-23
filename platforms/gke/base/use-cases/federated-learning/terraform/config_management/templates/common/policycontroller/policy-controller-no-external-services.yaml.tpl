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

---
# https://cloud.google.com/kubernetes-engine/enterprise/policy-controller/docs/latest/reference/constraint-template-library#k8snoexternalservices
---
# Prevent the creation of known resources that expose workloads to external IPs.
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sNoExternalServices
metadata:
  name: no-external-services
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Service"]
      - apiGroups: ["networking.k8s.io"]
        kinds: ["Ingress"]
      - apiGroups: ["gateway.networking.k8s.io"]
        kinds: ["Gateway"]
    excludedNamespaces:
      - "istio-egress"
      - "istio-ingress"
      - "istio-system"
%{ for namespace in external_services_allowed_namespaces ~}
      - "${namespace}"
%{ endfor ~}
---
# Requires that STRICT Istio mutual TLS is always specified when using
# PeerAuthentication. This constraint also ensures that the deprecated Policy
# and MeshPolicy resources enforce STRICT mutual TLS.
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: PolicyStrictOnly
metadata:
  name: peerauthentication-strict-constraint
spec:
  match:
    kinds:
      - apiGroups:
          - security.istio.io
        kinds:
          - PeerAuthentication
    excludedNamespaces:
%{ for namespace in external_services_allowed_namespaces ~}
      - "${namespace}"
%{ endfor ~}
---
# Enforce all PeerAuthentications cannot overwrite strict mtls
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: AsmPeerAuthnStrictMtls
metadata:
  name: asm-peer-authn-strict-mtls-constraint
spec:
  match:
    kinds:
      - apiGroups:
          - security.istio.io
        kinds:
          - PeerAuthentication
    excludedNamespaces:
%{ for namespace in external_services_allowed_namespaces ~}
      - "${namespace}"
%{ endfor ~}
  parameters:
    strictnessLevel: High
