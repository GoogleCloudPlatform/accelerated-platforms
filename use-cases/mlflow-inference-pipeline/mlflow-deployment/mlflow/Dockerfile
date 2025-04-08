FROM python:3.12.4-slim

RUN apt-get update && \
    apt-get -y --no-install-recommends install python3-dev gcc python3-pip git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY requirements.txt /
RUN pip3 install --no-cache-dir -r requirements.txt
ENV PYTHONUNBUFFERED 1
ENV PGPASSWORD=""
EXPOSE 5000

# Run the MLflow server 
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri","V_MLFLOW_DATABASE_URI" , "--default-artifact-root", "gs://V_MLFLOW_DATABASE_URI"]
