FROM python:3.11.10-slim-bookworm

RUN apt-get update && \
    apt-get -y --no-install-recommends install python3-dev gcc python3-pip git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /

RUN pip3 install --no-cache-dir -r /requirements.txt

COPY backend_service.py /

ENV PYTHONUNBUFFERED 1

CMD python3 /backend_service.py
