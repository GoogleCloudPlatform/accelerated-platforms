import psycopg2
from google.cloud import alloydb_v1 as alloydb

def execute_sql(host, database, user, password, cmd):
    """Creates a new database in PostgreSQL using psycopg2."""

    try:
        # Connect to an existing database (e.g., 'postgres')
        conn = psycopg2.connect(
            host=host, database=database, user=user, password=password
        )

        conn.autocommit = True  # Enable autocommit mode

        # Create a cursor object
        cursor = conn.cursor()

        # Execute the CREATE DATABASE command
        response = cursor.execute(cmd)
        print(f"SQL command:  '{cmd}' executed successfully.")

        # Handle the response
        print(response)
    except Exception as e:
        print(f"Error while executing SQL command {cmd} {e}")

    finally:
        # Close the cursor and connection
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def enable_google_ml_integration_ext(host, database_name, username, password):    
    # Install the latest google_ml_integration>=1.1 version available to your AlloyDB cluster, run this SQL command:
    cmd1 = "CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;"
    execute_sql(host, database_name, username, password, cmd1)
    
    # To work with vector embeddings, you must enable the pgvector extension.
    cmd2 = "CREATE EXTENSION IF NOT EXISTS vector;"
    execute_sql(host, database_name, username, password, cmd2)
    
    # To list the extensions your database has enabled, run this SQL command:
    cmd3 = "select extname, extversion from pg_extension;"
    execute_sql(host, database_name, username, password, cmd3)

    # Add columns for test, image and multi modal embeddings
    
    cmd4 = "ALTER TABLE {table_name} ADD COLUMN text_embedding vector(768);"
    cmd5 = "ALTER TABLE {table_name} ADD COLUMN image_embedding vector(768);"
    cmd6 = "ALTER TABLE {table_name} ADD COLUMN multimodal_embedding vector(768);"

'''
# ToDo: This lib function is not working?
# google.api_core.exceptions.InvalidArgument: 400 Malformed collection name: 'clusters/supportedDatabaseFlags'
def list_supported_database_flags(project_id, region, cluster_id):
    # Create a client
    client = alloydb.AlloyDBAdminClient()

    # Initialize request argument(s)
    request = alloydb.ListSupportedDatabaseFlagsRequest(
        parent="projects/{}/locations/{}/clusters/{}".format(
            project_id, region, cluster_id
        ),
    )

    # Make the request
    page_result = client.list_supported_database_flags(request=request)

    # Handle the response
    for response in page_result:
        print(response)

# ToDo: This is not working for enabling flag: 403 Permission denied on resource project primary-instance
def execute_sql_sdk(project_id, region, cluster_id, instance_id, database_name, username, password, sql_statement):
    try:
        # Create a client
        client = alloydb.AlloyDBAdminClient()
        instance = client.get_instance(
        name="projects/{}/locations/{}/clusters/{}/instances/{}".format(project_id, region, cluster_id, instance_id)
        )
        
        request = alloydb.ExecuteSqlRequest(
            instance=instance,
            database=database_name,
            user=username,
            password=password,
            sql_statement=sql_statement,
        )
        # Make the request
        response = client.execute_sql(request=request)

        # Handle the response
        print(response)
    except Exception as e:
        print(f"Error while executing sql cmd {sql_statement}: {e}")

def enable_google_ml_integration_ext(project_id, region, cluster_id, instance_id, database_name, username, password):
    # Install the latest google_ml_integration>=1.1 version available to your AlloyDB cluster, run this SQL command:
    cmd1 = "CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;"
    execute_sql_sdk(project_id, region, cluster_id, instance_id, database_name, username, password, cmd1)
    
    # To work with vector embeddings, you must enable the pgvector extension.
    cmd2 = "CREATE EXTENSION IF NOT EXISTS vector;"
    execute_sql_sdk(project_id, region, cluster_id, instance_id, database_name, username, password, cmd2)
    
    # To list the extensions your database has enabled, run this SQL command:
    cmd3 = "select extname, extversion from pg_extension;"
    execute_sql_sdk(project_id, region, cluster_id, instance_id, database_name, username, password, cmd3)

    # Add columns for test, image and multi modal embeddings
    cmd4 = "ALTER TABLE {table_name} ADD COLUMN text_embedding vector(768);"
    cmd5 = "ALTER TABLE {table_name} ADD COLUMN image_embedding vector(768);"
    cmd6 = "ALTER TABLE {table_name} ADD COLUMN multimodal_embedding vector(768);"

'''