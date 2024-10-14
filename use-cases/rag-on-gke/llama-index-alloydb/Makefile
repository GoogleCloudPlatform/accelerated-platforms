
config:
	kubectl create configmap query-gradio --from-file=query_alloydb.py=query_alloydb.py --from-file=query.py=query.py --from-file=requirements.in=requirements.in --dry-run=client -o yaml|kubectl apply -f -
