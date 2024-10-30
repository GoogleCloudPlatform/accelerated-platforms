1. set HF Tiken
HF__TOKE=

kubectl create secret generic hf-secret \
--from-literal=hf_api_token=${HF_TOKEN} \
--dry-run=client -o yaml | kubectl apply -n ${MLP_KUBERNETES_NAMESPACE} -f -

kubectl apply -f deployment.yaml -n ml-team

