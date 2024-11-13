# Dockerfile
FROM python:3.9-slim-buster

WORKDIR /app

COPY embedding.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt


CMD ["python", "embedding.py"]