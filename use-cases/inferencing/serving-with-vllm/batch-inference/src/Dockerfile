FROM python:3.12.4-slim

RUN apt-get update && \
    apt-get -y --no-install-recommends install python3-dev gcc python3-pip git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /

RUN pip3 install --no-cache-dir -r requirements.txt

COPY custom_json_formatter.py logging.conf run_batch_predictions.py /

ENV PYTHONUNBUFFERED 1

CMD python3 /run_batch_predictions.py
