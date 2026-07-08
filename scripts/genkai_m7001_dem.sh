#!/bin/bash
# Grid the M7001 T.P. soundings into a bathymetric DEM (GMT splines in tension,
# the GEBCO/NOAA-standard method) over the Tokyo Bay window -> a CF NetCDF in
# $DATA_DIR/bathymetry/M7001/TP/. See docs/dem.md.
#
#   pjsub scripts/genkai_m7001_dem.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=4
#PJM -L elapse=00:20:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export GMT_SESSION_NAME="dem_${PJM_JOBID:-$$}"
# The job calls the env python directly (no `conda activate`), so point PROJ/GDAL
# at the env's data dirs (else geopandas/pyogrio warns "proj_create_from_database").
export PROJ_DATA="${HOME}/mambaforge/envs/topobathy/share/proj"
export GDAL_DATA="${HOME}/mambaforge/envs/topobathy/share/gdal"

: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"

PY="${HOME}/mambaforge/envs/topobathy/bin/python"
cd "${HOME}/Github/topobathy"
TP="${DATA_DIR}/bathymetry/M7001/TP"

# Tokyo Bay DEM: ~0.002° (~180 m) grid, tension 0.35, 2 km coverage mask.
"${PY}" -m topobathy.cli.m7001_dem \
    --region 139.55 140.30 34.90 35.75 --spacing 0.002 --tension 0.35 --mask-km 2.0 \
    --out "${TP}/M7001_dem_tokyobay.nc"

echo "done."
