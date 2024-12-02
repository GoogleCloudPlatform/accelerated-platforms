import pg8000
import sqlalchemy
from google.cloud.alloydb.connector import Connector, IPTypes


def create_sqlalchemy_engine(
    inst_uri: str,
    user: str,
    # password: str,
    db: str,
    refresh_strategy: str = "background",
) -> tuple[sqlalchemy.engine.Engine, Connector]:
    connector = Connector(refresh_strategy=refresh_strategy)

    def getconn() -> pg8000.dbapi.Connection:
        conn: pg8000.dbapi.Connection = connector.connect(
            inst_uri,
            "pg8000",
            user=user,
            # password=password,
            db=db,
            ip_type=IPTypes.PUBLIC,
            enable_iam_auth=True,
        )
        return conn

    # create SQLAlchemy connection pool
    engine = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    engine.dialect.description_encoding = None
    return engine, connector


instance_uri = "projects/gkebatchenv3a4ec43f/locations/us-central1/clusters/mlp-ishmeet-rag/instances/mlp-ishmeet-rag-primary"
# db_user = "postgres"
# db_pass = "postgres"
db_user = "wi-mlp-ishmeet-rag-db-admin@gkebatchenv3a4ec43f.iam"
# db_name = "postgres"
db_name = "product_catalog"
# create_sqlalchemy_engine(instance_uri, db_user, db_pass, db_name)
engine, connector = create_sqlalchemy_engine(
    instance_uri,
    db_user,
    # db_pass,
    db_name,
)
# SQL query to add new rows to the 'weather' table with city values
# sql = """
# INSERT INTO weather (cities)
# VALUES
# ('New York'),
# ('Los Angeles'),
# ('Chicago');
# """

# with engine.connect() as conn:
#     conn.execute(sqlalchemy.text(sql))
#     conn.commit()  # Commit the changes to the database
#     conn.close()

# Verification query (optional)
# sql = "SELECT image_uri FROM clothes LIMIT 10;"
sql = """
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'clothes'
"""
with engine.connect() as conn:
    result = conn.execute(sqlalchemy.text(sql))
    for row in result:
        print(row)
    conn.close()
connector.close()
