from alloydb_setup import *
from create_catalog import *
from enable_google_ml_int import *
from google.cloud import alloydb_v1 as alloydb

# TODO: Variablize
# AlloyDB
project_id = "gkebatchexpce3c8dcb"
region = "us-central1"
cluster_id = "rag-cluster"
instance_id = "primary-instance"
no_of_cpu = 2
gke_vpc = "ml-vpc-karajendran"

# User
password = "retail"
admin_user = "catalog-admin"
admin_user_pass = "retail"

# Catalog
database_name = "postgres"
catalog_db = "flipkart"
catalog_table = "flipkart"
processed_data_path = "gs://gkebatchexpce3c8dcb-karajendran-data/flipkart_preprocessed_dataset/flipkart.csv"


if __name__ == "__main__":
    '''
    # Create a primary Cluster
    create_alloydb_cluster(
        project_id, region, cluster_id, instance_id, password, gke_vpc
    )

    # Create Primary Instance
    create_alloydb_instance(project_id, region, cluster_id, instance_id, no_of_cpu)

    # Create additional users
    create_alloydb_user(
        project_id,
        region,
        cluster_id,
        admin_user,
        admin_user_pass,
        "ALLOYDB_BUILT_IN",
        ["alloydbsuperuser"],
    )
 
    # List the users
    list_users(project_id, region, cluster_id)
   '''
    # Get the IP address of the primary instance
    client = alloydb.AlloyDBAdminClient()
    instance = client.get_instance(
        name="projects/{}/locations/{}/clusters/{}/instances/{}".format(
            project_id, region, cluster_id, instance_id
        )
    )
    ip_address = instance.ip_address
    '''
    # Create flipkart database
    create_database(ip_address, database_name, admin_user, admin_user_pass, catalog_db)

    # Upload catalog to flipkart database
    create_and_populate_table(
        ip_address,
        catalog_db,
        admin_user,
        admin_user_pass,
        catalog_table,
        processed_data_path,
    )
    '''
    
    #enable_google_ml_integration_ext(project_id, region, cluster_id, instance_id, catalog_db, admin_user, admin_user_pass)
    enable_google_ml_integration_ext(ip_address, catalog_db, admin_user, admin_user_pass)
    #list_supported_database_flags(project_id, region, cluster_id)