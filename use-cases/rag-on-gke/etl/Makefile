
config:
	kubectl create configmap rag-etl --from-file=populate_data.py=populate_data.py --from-file=requirements.in=requirements.in --dry-run=client -o yaml|kubectl apply -f -
