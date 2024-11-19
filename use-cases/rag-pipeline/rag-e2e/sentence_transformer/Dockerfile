# Dockerfile
FROM python:3.13.0-slim

WORKDIR /app

COPY embedding.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "embedding.py"]
