from google.cloud import alloydb_v1 as alloydb
import google.api_core.exceptions
import logging

logging.basicConfig(level=logging.INFO)

client = alloydb.AlloyDBAdminClient()


def create_alloydb_cluster(project_id, region, cluster_id, password, gke_vpc):
    """Creates an AlloyDB cluster."""
    try:
        cluster = alloydb.Cluster(
            network=f"projects/{project_id}/global/networks/{gke_vpc}"
        )
        request = alloydb.CreateClusterRequest(
            parent=f"projects/{project_id}/locations/{region}",
            cluster_id=cluster_id,
            cluster=cluster,
        )
        operation = client.create_cluster(request=request)
        logging.info("Waiting for Cluster creation to complete...")
        response = operation.result()
        logging.info(f"Cluster created: {response.name}")
        return response
    except google.api_core.exceptions.GoogleAPIError as e:
        logging.error(f"Error creating cluster: {e}")
        raise


def create_alloydb_instance(project_id, region, cluster_id, instance_id, no_of_cpu):
    """Creates an AlloyDB primary instance."""
    try:
        instance = alloydb.Instance(
            machine_config=alloydb.Instance.MachineConfig(cpu_count=no_of_cpu),
            instance_type="PRIMARY",
        )
        request = alloydb.CreateInstanceRequest(
            parent=f"projects/{project_id}/locations/{region}/clusters/{cluster_id}",
            instance_id=instance_id,
            instance=instance,
        )
        operation = client.create_instance(request=request)
        logging.info("Waiting for Instance creation to complete...")
        response = operation.result()
        logging.info(f"Instance created: {response.name}")
        return response
    except google.api_core.exceptions.GoogleAPIError as e:
        logging.error(f"Error creating instance: {e}")
        raise


def create_alloydb_user(
    project_id, region, cluster_id, username, password, user_type, database_roles
):
    """Creates a user in the AlloyDB cluster."""
    try:
        user = alloydb.User(
            user_type=user_type,
            database_roles=database_roles,
            password=password,
        )
        request = alloydb.CreateUserRequest(
            parent=f"projects/{project_id}/locations/{region}/clusters/{cluster_id}",
            user_id=username,
            user=user,
        )
        client.create_user(request=request)
        logging.info(f"User created: {username}")
    except google.api_core.exceptions.GoogleAPIError as e:
        logging.error(f"Error creating user: {e}")
        raise


def create_alloydb_iam_user(
    project_id, region, cluster_id, username, user_type, database_roles
):
    """Creates a user in the AlloyDB cluster."""
    try:
        user = alloydb.User(
            user_type=user_type,
            database_roles=database_roles,
        )
        request = alloydb.CreateUserRequest(
            parent=f"projects/{project_id}/locations/{region}/clusters/{cluster_id}",
            user_id=username,
            user=user,
        )
        client.create_user(request=request)
        logging.info(f"User created: {username}")
    except google.api_core.exceptions.GoogleAPIError as e:
        logging.error(f"Error creating user: {e}")
        raise


def list_users(project_id, region, cluster_id):
    """Lists users in the AlloyDB cluster."""
    try:
        request = alloydb.ListUsersRequest(
            parent=f"projects/{project_id}/locations/{region}/clusters/{cluster_id}"
        )
        page_result = client.list_users(request=request)
        for user in page_result:
            logging.info(f"User: {user}")
    except google.api_core.exceptions.GoogleAPIError as e:
        logging.error(f"Error listing users: {e}")
        raise


def get_connection_info(project_id, region, cluster_id, instance_id):
    """Gets connection information for the AlloyDB instance."""
    try:
        instance_name = f"projects/{project_id}/locations/{region}/clusters/{cluster_id}/instances/{instance_id}"
        request = alloydb.GetConnectionInfoRequest(parent=instance_name)
        connection_info = client.get_connection_info(request=request)
        logging.info(f"Connection info: {connection_info}")
        return connection_info
    except google.api_core.exceptions.GoogleAPIError as e:
        logging.error(f"Error getting connection info: {e}")
        raise


def delete_alloydb_cluster(project_id, region, cluster_id):
    """Deletes an AlloyDB cluster."""
    try:
        request = alloydb.DeleteClusterRequest(
            name=f"projects/{project_id}/locations/{region}/clusters/{cluster_id}"
        )
        operation = client.delete_cluster(request=request)
        logging.info("Waiting for Cluster deletion to complete...")
        operation.result()
        logging.info(f"Cluster deleted: {cluster_id}")
    except google.api_core.exceptions.GoogleAPIError as e:
        logging.error(f"Error deleting cluster: {e}")
        raise
