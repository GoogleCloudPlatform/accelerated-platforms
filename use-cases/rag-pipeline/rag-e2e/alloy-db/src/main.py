from alloydb_setup import *
from create_catalog import *
from enable_google_ml_int import *


# TODO: Variablize

# AlloyDB
project_id = "gkebatchexpce3c8dcb"
region = "us-central1"
cluster_id = "rag-db-karajendran"
instance_id = "primary-instance"
no_of_cpu = 2
gke_vpc = "ml-vpc-karajendran"
instance_uri = f"projects/{project_id}/locations/{region}/clusters/{cluster_id}/instances/{instance_id}"

# User
password = "retail"  # postgres user
username = "catalog-admin"
user_password = "retail"
user_type = "ALLOYDB_BUILT_IN"
database_roles = ["alloydbsuperuser"]

# IAM User
iam_username = "alloydb-access-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com"
iam_user_type = "ALLOYDB_IAM_USER"
iam_database_roles = ["alloydbiamuser"]

# Catalog
database_name = "postgres"
catalog_db = "product_catalog"
catalog_table = "clothes"

# processed_data_path = "gs://gkebatchexpce3c8dcb-karajendran-data/flipkart_preprocessed_dataset/flipkart.csv"

processed_data_path = (
    "gs://gkebatchexpce3c8dcb-karajendran-data/RAG/master_product_catalog.csv"
)

# Vector Index
EMBEDDING_COLUMN = "text_embeddings"
INDEX_NAME = "rag_text_embeddings_index"
DISTANCE_FUNCTION = "cosine"
NUM_LEAVES_VALUE = 300  # random guess for now

if __name__ == "__main__":
    try:

        # Create AlloyDB cluster
        create_alloydb_cluster(
            project_id,
            region,
            cluster_id,
            password,
            gke_vpc,
        )
        # Create AlloyDB instance
        create_alloydb_instance(
            project_id,
            region,
            cluster_id,
            instance_id,
            no_of_cpu,
        )
        # Create AlloyDB Users
        create_alloydb_user(
            project_id,
            region,
            cluster_id,
            username,
            user_password,
            user_type,
            database_roles,
        )

        create_alloydb_iam_user(
            project_id,
            region,
            cluster_id,
            iam_username,
            iam_user_type,
            iam_database_roles,
        )
        # List users
        list_users(project_id, region, cluster_id)

        # Create Database - This function enables the vector, scann extensions as well
        create_database_old(
            instance_uri,
            database_name,
            catalog_db,
            username,
            user_password,
        )

        # Get DB connection info
        connection_info = get_connection_info(
            project_id, region, cluster_id, instance_id
        )
        host = connection_info.ip_address
        logging.info(f"AlloyDb ip address: {host}")
        create_database(
            host,
            database_name,
            catalog_db,
            username,
            user_password,
        )

        # ETL
        create_and_populate_table(
            instance_uri,
            catalog_db,
            username,
            user_password,
            catalog_table,
            processed_data_path,
        )

        # Create Vector Index
        engine = create_alloydb_engine(
            instance_uri,
            catalog_db,
            username,
            user_password,
        )
        create_text_embeddings_index(
            engine,
            catalog_table,
            EMBEDDING_COLUMN,
            INDEX_NAME,
            DISTANCE_FUNCTION,
            NUM_LEAVES_VALUE,
        )

    finally:
        # Clean up resources (optional, uncomment if needed)
        # delete_alloydb_cluster(project_id, region, cluster_id)
        pass
