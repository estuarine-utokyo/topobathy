#!/bin/bash
# List mound candidates (no slope filter) in the Boso close-up with width and slope,
# to choose the slope threshold. Figure goes to scratch-like logs/, not docs/.
#
#   pjsub -o logs/list_boso_mounds.%j.log scripts/genkai_list_boso_mounds.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=2
#PJM -L elapse=00:15:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
"${ENV}/bin/python" scripts/plot_depth_map.py \
    --dem "${DATA_DIR}/geodata/bathymetry/M7001/TP/M7001_dem_tokyobay_50m_chiba_channel.nc" \
    --region 139.995 140.044 35.48 35.52 --vmax 20 --fine-to 20 --fill-gaps \
    --mounds --mound-depth 7 14 --mound-prominence ${PROM:-1} --mound-shore-dist 2000 \
    --no-title --no-note --out logs/boso_mounds_candidates.png
