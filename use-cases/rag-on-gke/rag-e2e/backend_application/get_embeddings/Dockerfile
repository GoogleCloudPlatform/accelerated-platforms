FROM python:3.10-slim-buster

WORKDIR /app

COPY get_emb.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "get_emb.py"]
