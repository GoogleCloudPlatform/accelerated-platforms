FROM python:3.12.4-slim

RUN apt-get update && \
    apt-get -y --no-install-recommends install python3-dev gcc python3-pip git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY requirements.txt /
RUN pip3 install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED 1
ENV PGPASSWORD=""
ENV MLP_MLFLOW_DATABASE_URI=postgresql+psycopg2://wi-mlp-mlflow-prod-db-admin@gkebatchenv3a4ec43f.iam:@127.0.0.1:5432/mlflowdb
ENV MLP_MLFLOW_ARTIFACT_LOCATION=gkebatchenv3a4ec43f-mlflow-prod-mlflow
EXPOSE 5000

# Run the MLflow server 
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri","${MLP_MLFLOW_DATABASE_URI}" , "--default-artifact-root", "${MLP_MLFLOW_ARTIFACT_LOCATION}"]
