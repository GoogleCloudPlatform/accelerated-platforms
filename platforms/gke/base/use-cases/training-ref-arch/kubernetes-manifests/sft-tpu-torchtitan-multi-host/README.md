# Multi-host TorchTitan TPU SFT Kubernetes Manifests

Kustomize base and overlays for multi-host Supervised Fine-Tuning (SFT) on Cloud
TPU v6e slices (`tpu-v6e-4x4`, 16 chips across 4 `ct6e-standard-4t` nodes)
orchestrated with Kubernetes `JobSet` (`jobset.x-k8s.io/v1alpha2`), PyTorch
`torch_tpu`, and TorchTitan.

See the step-by-step guide in
[Multi-host Supervised Fine-Tuning (SFT) with TPUs on GKE using TorchTitan](/docs/platforms/gke/base/use-cases/training-ref-arch/sft-tpu-torchtitan-multi-host/README.md).
