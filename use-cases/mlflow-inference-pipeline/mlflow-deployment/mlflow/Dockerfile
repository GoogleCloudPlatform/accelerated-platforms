FROM python:3.12.4-slim

ENV PYTHONUNBUFFERED 1
ENV PGPASSWORD=""

RUN apt-get update && \
    apt-get -y --no-install-recommends install \
    gcc \
    git \
    python3-dev  \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY requirements.txt /
RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Run the MLflow server 
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]
