# openeo-xarray-executor

## General
The openEO executor based on xarray (EODC/EURAC backend). The executor is seperated from the api in this repo. Initially forked from [here](https://github.com/eodcgmbh/openeo-argoworkflows) where api and executor are together in one repo.

## Example run command for docker

```
docker run \
  -v /dss:/dss \
  -e STAC_API_URL=https://stac.terrabyte.lrz.de/public/api \
  -v ./output:/user_data \
  openeo-executor \
  openeo_executor execute \
  --process_graph '{
    "id": "0D31CB857AC948944448",
    "process_graph": {
      "load1": {
        "process_id": "load_collection",
        "arguments": {
          "id": "sentinel-2-c1-l2a",
          "spatial_extent": {
            "west": 11.50491714477539,
            "east": 11.55641555786133,
            "south": 48.0802580060505,
            "north": 48.103189907601454
          },
          "temporal_extent": ["2025-11-30", "2025-12-04"],
          "bands": ["AOT"],
          "properties": {}
        }
      },
      "save2": {
        "process_id": "save_result",
        "arguments": {
          "data": {"from_node": "load1"},
          "format": "GTIFF"
        },
        "result": true
      }
    },
    "parameters": []
  }' \
  --user_profile '{"OPENEO_USER_ID":"TEST", "OPENEO_JOB_ID":"TEST_JOB","OPENEO_USER_WORKSPACE":"/user_data"}' \
  --dask_profile '{"LOCAL": true}'
```

## Conversion from Docker to Charliecloud for HPC
To create a charliecloud image .sqfs from the Dockerfile for the use on tb:
- create a .tar from the Dockerimage: `docker save openeo-executor:latest -o openeo-executor.tar` 
- copy the .tar to the terrabyte login node: `scp openeo-executor.tar <user_id>@login.terrabyte.lrz.de:/path/to/your/dss/folder/` 
- use the latest stable charliecloud version (0.4) there `module load charliecloud/0.40`
- convert the Dockerimage to a .sqfs: `ch-convert openeo-executor.tar openeo-executor.sqfs`
- or follow: https://docs.terrabyte.lrz.de/software/containers/charliecloud/#generate-a-charliecloud-image-from-a-dockerfile

## Example run command for charliecloud
Here is an example sbatch skript for usage on HPC. This is useful for testing and debugging without interacting with the openEO API: [sbatch.sh](sbatch.sh)

