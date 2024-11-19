1. set HF Tiken
HF__TOKE=<your token>

kubectl create secret generic hf-secret \
--from-literal=hf_api_token=${HF_TOKEN} \
--dry-run=client -o yaml | kubectl apply -n ${MLP_KUBERNETES_NAMESPACE} -f -

kubectl apply -f provisioning-request-l4.yaml -n ml-team
kubectl apply -f it-model-deployment.yaml -n ml-team

kubectl delete -f it-model-deployment.yaml -n ml-team
kubectl delete -f provisioning-request-l4.yaml -n ml-team
