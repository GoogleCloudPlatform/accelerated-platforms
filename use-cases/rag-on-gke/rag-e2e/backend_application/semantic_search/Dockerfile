FROM python:3.10-slim-buster

WORKDIR /app

COPY main.py requirements.txt get_emb.py ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]


