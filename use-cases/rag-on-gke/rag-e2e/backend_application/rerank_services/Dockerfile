# Dockerfile for the VLLM client
FROM python:3.10-slim-buster

WORKDIR /app

COPY rerank.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "rerank.py"]
