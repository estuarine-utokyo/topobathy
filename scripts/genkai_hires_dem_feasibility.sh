#!/bin/bash
# Feasibility of a 10 m / 5 m Tokyo Bay DEM: M7001 point density and pilot gridding cost.
#
#   pjsub -o logs/hires_dem_feasibility.%j.log scripts/genkai_hires_dem_feasibility.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=8
#PJM -L elapse=02:00:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export GMT_SESSION_NAME="hires_${PJM_JOBID:-$$}"
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
/usr/bin/time -v "${ENV}/bin/python" scripts/hires_dem_feasibility.py 2>&1 | grep -v -i warn
