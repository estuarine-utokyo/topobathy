#!/bin/bash
# Depth map of inner Tokyo Bay (north of Kisarazu) from the older CAO 30 m grid
# (areas 0030-11..15, merged to lat/lon in 2020), same style as the M7001 map.
#
#   pjsub -o logs/plot_inner_bay_depth_cao30m_2020.%j.log scripts/genkai_plot_inner_bay_depth_cao30m_2020.sh
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
"${ENV}/bin/python" scripts/plot_depth_map.py \
    --dem "${DATA_DIR}/geodata/bathymetry/tokyo_bay/depth_0030-11+12+13+14+15.nc" \
    --var Band1 --region 139.60 140.15 35.36 35.72 --vmax 30 --cmap deep \
    --title "Inner Tokyo Bay: depth, older CAO 30 m grid" \
    --source-note "Source: Cabinet Office, Tokyo Inland Earthquake Model Study Group, 30 m grid, areas 0030-11 to 15, merged to lat/lon in 2020; land: OpenStreetMap via xcoast." \
    --out docs/figures/tokyobay_inner_depth_cao30m_2020.png
