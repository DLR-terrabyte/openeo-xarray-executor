#!/bin/bash

#SBATCH -J openeo_test_graph
#SBATCH -o <adapt to where you want to log>/logs/%j_stdout.logfile
#SBATCH -e <adapt to where you want to log>/logs/%j_sterr.logfile
#SBATCH -D <adapt to working directory>
#SBATCH --get-user-env
#SBATCH --clusters=hpda2
#SBATCH --partition=hpda2_test
#SBATCH --cpus-per-task=2
#SBATCH --mem=2gb
#SBATCH --mail-type=NONE
#SBATCH --export=NONE
#SBATCH --time=00:05:00
#SBATCH --account=hpda-c

# load modules
module load slurm_setup
module load charliecloud/0.40

# log start
echo "START JOB: $SLURM_JOB_ID"

# log sbatch params
echo "SLURM_JOB_NAME: $SLURM_JOB_NAME"
echo "SLURM_JOB_ID: $SLURM_JOB_ID"
echo "USER: $USER"
echo "UID: $UID"

# base path: scratch + slurm job id
BASEDIR="$SCRATCH_DLR/$SLURM_JOB_ID"

# default tmpdir
echo "TMPDIR Default: $TMPDIR"

# make tmp dir
mkdir -p "$BASEDIR/tmp"
export TMPDIR="$BASEDIR/tmp" # by exporting it here it is automatically availalble to ch-run (?)
echo "TMPDIR Updated: $TMPDIR"

# ML ENV
mkdir -p "$TMPDIR/openeo_ml_cache/"
export OPD_ML_CACHE_DIR="$TMPDIR/openeo_ml_cache"
echo "OPD_ML_CACHE_DIR: $OPD_ML_CACHE_DIR"

mkdir -p "$TMPDIR/openeo_ml_tmp/"
export OPD_ML_TMP_DIR="$TMPDIR/openeo_ml_tmp"
echo "OPD_ML_TMP_DIR: $OPD_ML_TMP_DIR"

export OPD_ML_MODEL_EXECUTION_MODE="subprocess" # dask or subprocess
echo "OPD_ML_MODEL_EXECUTION_MODE: $OPD_ML_MODEL_EXECUTION_MODE"

export OPD_ML_ALLOWED_MLM_PROCESSING_PACKAGES="ml_datacube_bridge"
echo "OPD_ML_ALLOWED_MLM_PROCESSING_PACKAGES: $OPD_ML_ALLOWED_MLM_PROCESSING_PACKAGES"

#mkdir -p "$OPD_ML_CACHE_DIR" "$OPD_ML_TMP_DIR"

# make output dir with SLURM_JOB_ID
mkdir -p "$BASEDIR/output/"
OUTPUT_DIR="$BASEDIR/output"
echo "OUTPUT_DIR: $OUTPUT_DIR"

# log ch-run
echo "################# Executing Container: Start ##############"
>&2 echo "################# Executing Container: Start ##############"

set -x # logging also the ch-run command
ch-run \
  --bind=/dss/.:/dss/ \
  --bind="$OUTPUT_DIR":/user_data \
  --set-env=STAC_API_URL=https://stac.terrabyte.lrz.de/public/api \
  --set-env=OPD_ML_CACHE_DIR="$OPD_ML_CACHE_DIR" \
  --set-env=OPD_ML_TMP_DIR="$OPD_ML_TMP_DIR" \
  --set-env=OPD_ML_MODEL_EXECUTION_MODE="$OPD_ML_MODEL_EXECUTION_MODE" \
  --set-env=OPD_ML_ALLOWED_MLM_PROCESSING_PACKAGES="$OPD_ML_ALLOWED_MLM_PROCESSING_PACKAGES" \
  --write-fake <path to your charliecloud .sqfs file> -- \
  /opt/openeo_xarray_executor/.venv/bin/openeo_executor execute \
  --process_graph '{"id":"0D31CB857AC948944448","process_graph":{"load1":{"process_id":"load_collection","arguments":{"id":"sentinel-2-c1-l2a","spatial_extent":{"west":11.50491714477539,"east":11.55641555786133,"south":48.0802580060505,"north":48.103189907601454},"temporal_extent":["2025-11-30T23:00:00.000Z","2025-12-04T23:00:00.000Z"],"bands":["AOT"],"properties":{}}},"save2":{"process_id":"save_result","arguments":{"data":{"from_node":"load1"},"format":"GTIFF"},"result":true}},"parameters":[]}' \
  --user_profile '{"OPENEO_USER_ID":"TEST","OPENEO_JOB_ID":"TEST_JOB","OPENEO_USER_WORKSPACE":"/user_data"}' \
  --dask_profile '{"LOCAL": true}'
set +x

echo "################# Executing Container: Done ##############"
>&2 echo "################# Executing Container: Done ##############"

# log done
echo "DONE JOB: $SLURM_JOB_ID"

