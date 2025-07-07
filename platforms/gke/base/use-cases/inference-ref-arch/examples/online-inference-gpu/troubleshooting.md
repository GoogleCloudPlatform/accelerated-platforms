## Online inference with GPUs Troubleshooting

This section describes common issues and troubleshooting steps.

### Node provisioning

- If the online inference workload Pod doesn't trigger a node scale up, and
  remains in pending state, check if its events contain something like:

  ```
  kubectl describe pod <POD_NAME>
  ```

  Where:

  - `<POD_NAME>` is the name of the Pod running the online inference workload.
    `<POD_NAME>` starts with the `vllm-` prefix.

  In case this happens, try deleting the Pod after the ProvisioningRequest is
  reported with the status of `Provisioned=True`. To get the list of ``s, run
  the following command:

  ```shell
  kubectl get provisioningrequest.autoscaling.x-k8s.io
  ```

  The output is similar to the following:

  ```text
  NAME        ACCEPTED   PROVISIONED   FAILED   AGE
  vllm-h100   True       True                   10m
  ```

  To delete the online inference workload pod, run the following command:

  ```shell
  kubectl delete pod <POD_NAME>
  ```

  Where:

  - `<POD_NAME>` is the name of the Pod running the online inference workload.
    `<POD_NAME>` starts with the `vllm-` prefix.

  Google Kubernetes Engine (GKE) takes care of recreating the Pod.
