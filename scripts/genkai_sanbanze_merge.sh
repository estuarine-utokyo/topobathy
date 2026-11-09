#!/bin/bash
# Merge the Chiba Prefecture Sanbanze surveys (10 m, A.P.) into the Futtsu-merged 50 m and 10 m
# Tokyo Bay DEMs. Writes staging files (check them, then give them the default names).
#
#   pjsub -o logs/sanbanze_merge.%j.log scripts/genkai_sanbanze_merge.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=8
#PJM -L elapse=01:00:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
TP="${DATA_DIR}/geodata/bathymetry/M7001/TP"
for R in 50m 10m; do
  "${ENV}/bin/python" scripts/sanbanze_merge.py \
      --base "${TP}/M7001_dem_tokyobay_${R}_futtsu.nc" \
      --out "${TP}/M7001_dem_tokyobay_${R}_sanbanze_staging.nc" \
      --diff-png "docs/figures/sanbanze_merge_diff_${R}.png"
done
