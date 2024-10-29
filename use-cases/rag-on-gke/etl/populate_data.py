from io import BytesIO, BufferedIOBase
import json
import logging
import os
from urllib import request, parse

import zipfile

import psycopg
import requests

logger = logging.getLogger(__name__)

CHUNKSIZE=16384

def download_from_kaggle(url) -> BytesIO:
    local_file = BytesIO()
    with requests.get(url, timeout=30, stream=True) as req:
        req.raise_for_status()
        for chunk in req.iter_content(chunk_size=CHUNKSIZE):
            local_file.write(chunk)
    local_file.seek(0)
    return local_file

def extract_file(f: BytesIO, filename: str) -> BufferedIOBase:
    z = zipfile.ZipFile(f)
    return z.open(filename)

def importdata(dbconn: psycopg.Connection,
               tablename: str,
               f: BufferedIOBase) -> int:
    cursor = dbconn.cursor()
    with cursor.copy((f"COPY {tablename}"
                      " FROM STDIN WITH (HEADER, FORMAT 'csv', DELIMITER ',')")) as copy:
        while data := f.read(CHUNKSIZE):
            copy.write(data)
    dbconn.commit()
    return cursor.rowcount

def create_table(dbconn, tablename, columns):
    cursor = dbconn.cursor()
    sql = f"CREATE TABLE IF NOT EXISTS {tablename} ("
    sql += "\n ,".join(f"{c} {t}" for c, t in columns)
    sql += ");"
    cursor.execute(sql)
    dbconn.commit()

def truncate_table(dbconn, tablename):
    cursor = dbconn.cursor()
    cursor.execute(f"truncate table {tablename};")
    dbconn.commit()

def drop_table(dbconn, tablename):
    cursor = dbconn.cursor()
    cursor.execute(f"drop table if exists {tablename};")
    dbconn.commit()

def embedding(dbconn, tablesrc, tabledest, col_id, col_text):
    drop_table(dbconn, tabledest)
    create_table(dbconn, tabledest,
                 [("uniq_id", "text"), ("embedding", "vector")])
    cursor = dbconn.cursor()
    cursor.execute(f"""insert into {tabledest} select
    {col_id}, google_ml.embedding_text({col_text}) from {tablesrc}
    where {col_text} is not null;""")
    dbconn.commit()
    return cursor.rowcount



def generate_db_url_from_workload_identity():
    urlbase = ("http://metadata.google.internal/"
               "computeMetadata/v1/instance/"
               "service-accounts/default/")
    req = request.Request(urlbase + "email",
                          headers={"Metadata-Flavor" :
                                   "Google"})
    rr = request.urlopen(req)
    email = rr.read().decode("utf8")
    rr.close()
    pguser = email.removesuffix(".gserviceaccount.com")
    req = request.Request(urlbase + "token",
                          headers={"Metadata-Flavor" :
                                   "Google"})
    rr = request.urlopen(req)
    t = json.load(rr)
    rr.close()
    pgpassword = t["access_token"]
    pghost = os.getenv("PGHOST")
    pgdatabase = os.getenv("PGDATABASE")
    return f"postgresql://{parse.quote(pguser)}:{pgpassword}@{pghost}/{pgdatabase}"


def main():
    DBURL = os.getenv("DB_URL")
    if not DBURL:
        DBURL = generate_db_url_from_workload_identity()
    logger.debug("Connecting to database: %s", DBURL)
    conn = psycopg.connect(DBURL)
    kaggle_file_url = os.getenv("DATA_URL")
    data_filename = os.getenv("DATAFILE")
    emb_t, col_id, col_text = os.getenv("EMBEDDING_DESC").split(":")
    datafile = extract_file(download_from_kaggle(kaggle_file_url),
                            data_filename)
    headers = datafile.readline().decode("utf8").strip()
    datafile.seek(0)
    columns = [(t, "text") for t in headers.split(",")]
    tablename = os.getenv("TABLENAME")
    if os.getenv("RECREATE"):
        drop_table(conn, tablename)
        logger.debug("DROPPED TABLE: %s", tablename)
    create_table(conn, tablename, columns)
    logger.debug("CREATED TABLE: %s", tablename)
    logger.info("Load data to %s, %d",
                tablename,
                importdata(conn, tablename, datafile))
    logger.info("Embedding to %s, %d",
                emb_t,
                embedding(conn, tablename, emb_t, col_id, col_text))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s %(levelname)s:%(message)s",
                        datefmt="%a, %d %b %Y  %T %z")
    main()
