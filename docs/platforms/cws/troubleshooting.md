# Cloud Workstations troubleshooting

## GitHub: GET `https://api.github.com/user`: 401 Bad credentials

```
╷
│ Error: Error waiting to create Connection: Error waiting for Creating Connection: Error code 9, message: failed to get authenticated user from GitHub: GET https://api.github.com/user: 401 Bad credentials []
│
│   with google_cloudbuildv2_connection.gc_cloud_workstation_image,
│   on cloudbuildv2_connection.tf line 15, in resource "google_cloudbuildv2_connection" "gc_cloud_workstation_image":
│   15: resource "google_cloudbuildv2_connection" "gc_cloud_workstation_image" {
│
╵
```

This error usually means that you are using a Fine grained token or that your
token in invalid. Try regenerating your Classic token and updating the secret.

## WorkstationCluster: Error 400: Resource '"..."' has nested resources.

```
╷
│ Error: Error when reading or editing WorkstationCluster: googleapi: Error 400: Resource '"projects/<project_id>/locations/<location>/workstationClusters/<workstation_cluster>"' has nested resources. If the API supports cascading delete, set 'force' to true to delete it and its nested resources.
│
│
╵
```

This error means that your workstation cluster still has workstation
configurations associated with it. Please delete any orphaned workstation
configurations and rerun the destroy.
