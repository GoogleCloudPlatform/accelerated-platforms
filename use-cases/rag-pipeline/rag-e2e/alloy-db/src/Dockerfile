FROM python:3.13.0-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY alloydb_setup.py .
COPY create_catalog.py .
COPY enable_google_ml_int.py .
COPY get_emb.py .
COPY main.py .

#CMD ["python", "alloydb_setup.py"]
#CMD ["python", "create_catalog.py"]
CMD ["python", "main.py"]