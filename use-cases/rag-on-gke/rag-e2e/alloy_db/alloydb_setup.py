from google.cloud import alloydb_v1 as alloydb

client = alloydb.AlloyDBAdminClient()


def create_alloydb_cluster(
    project_id, region, cluster_id, instance_id, password, gke_vpc
):
    """Creates an AlloyDB cluster and primary instance."""

    cluster = alloydb.Cluster()
    cluster.network = "projects/{}/global/networks/{}".format(project_id, gke_vpc)
    initial_user = (alloydb.User(password=password),)

    request = alloydb.CreateClusterRequest(
        parent="projects/{}/locations/{}".format(project_id, region),
        cluster_id=cluster_id,
        cluster=cluster,
    )

    operation = client.create_cluster(request=request)

    print("Waiting for Cluster creation to complete...")

    response = operation.result()

    # TODO: Handle the response
    print(response)


def create_alloydb_instance(project_id, region, cluster_id, instance_id, no_of_cpu):

    instance = alloydb.Instance(
        machine_config=alloydb.Instance.MachineConfig(
            {
                "cpu_count": no_of_cpu,
            }
        ),
    )
    instance.instance_type = "PRIMARY"

    request = alloydb.CreateInstanceRequest(
        parent="projects/{}/locations/{}/clusters/{}".format(
            project_id, region, cluster_id
        ),
        instance_id=instance_id,
        instance=instance,
    )

    operation = client.create_instance(request=request)

    print("Waiting for Instance creation to complete...")
    response = operation.result()

    # TODO: Handle the response
    print(response)


def create_alloydb_user(
    project_id, region, cluster_id, username, password, user_type, database_roles
):
    """Creates a user in the AlloyDB cluster."""
    user = alloydb.User(
        user_type=user_type,
        database_roles=database_roles,
        password=password,
    )

    request = alloydb.CreateUserRequest(
        parent="projects/{}/locations/{}/clusters/{}".format(
            project_id, region, cluster_id
        ),
        user_id=username,
        user=user,
    )

    client.create_user(request=request)


def list_users(project_id, region, cluster_id):

    # Initialize request argument(s)
    request = alloydb.ListUsersRequest(
        parent="projects/{}/locations/{}/clusters/{}".format(
            project_id, region, cluster_id
        ),
    )

    # Make the request
    page_result = client.list_users(request=request)

    # Handle the response
    for response in page_result:
        print(response)
