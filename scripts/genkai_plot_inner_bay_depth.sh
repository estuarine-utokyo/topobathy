#!/bin/bash
# Depth map of inner Tokyo Bay (north of Kisarazu) from the 50 m M7001 T.P. DEM,
# cmocean colours to 30 m, OSM land via xcoast -> docs/figures/.
#
#   pjsub scripts/genkai_plot_inner_bay_depth.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=2
#PJM -L elapse=00:20:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
# jsasaki 2026-10-24: the M7001-only DEM was renamed when Futtsu took the default name
"${ENV}/bin/python" scripts/plot_depth_map.py \
    --dem "${DATA_DIR}/geodata/bathymetry/M7001/TP/M7001_dem_tokyobay_50m_m7001_only.nc" \
    --region 139.60 140.15 35.36 35.72 --vmax 30 --cmap deep \
    --out docs/figures/tokyobay_inner_depth_tp.png
