# Cloud Workstations configuration

> [!NOTE]  
> The Cloud Workstations (CWS) Platform is currently in beta and is still being
> actively developed.

## Profiles

Different configuration profiles can be created and used by creating a directory
in
[`platforms/cws/_shared_config/profile`](/platforms/cws/_shared_config/profile),
a default profile is included and applied. To apply a different profile, use the
[`apply_profile.sh`](/platforms/cws/_shared_config/scripts/apply_profile.sh)
script in `/platforms/cws/_shared_config/scripts/`.

```shell
"${ACP_REPO_DIR}//platforms/cws/_shared_config/scripts/apply_profile.sh" <profile_name>
```

## Configuration files

### build (`platforms/cws/_shared_config/build.auto.tfvars`)

### comfyui (`platforms/cws/_shared_config/comfyui.auto.tfvars`)

### networking (`platforms/cws/_shared_config/networking.auto.tfvars`)

### platform (`platforms/cws/_shared_config/platform.auto.tfvars`)

### workstation_cluster (`platforms/cws/_shared_config/workstation_cluster.auto.tfvars`)
