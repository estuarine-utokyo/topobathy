#!/bin/bash
# Tokyo Bay depth map (T.P.) from the 50 m DEM (M7001 + Chiba channel + Futtsu), south to
# 35.2 N (Yokosuka): no title, no source line, larger labels, Boso close-up frame outlined.
#
#   pjsub -o logs/plot_tokyobay_depth_chiba_channel.%j.log scripts/genkai_plot_tokyobay_depth_chiba_channel.sh
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
#---> jsasaki 2026-10-24: the default DEM now includes Futtsu; medium PNGs (150 dpi);
# the map without the frame is drawn here too
DEM="${DATA_DIR}/geodata/bathymetry/M7001/TP/M7001_dem_tokyobay_50m.nc"
COMMON=(--region 139.60 140.15 35.20 35.72 --vmax 30 --no-title --no-note --font-size 14
        --cbar-label "Depth (m)" --dpi 150)
"${ENV}/bin/python" scripts/plot_depth_map.py --dem "${DEM}" "${COMMON[@]}" \
    --out docs/figures/tokyobay_depth_tp_chiba_channel.png
"${ENV}/bin/python" scripts/plot_depth_map.py --dem "${DEM}" "${COMMON[@]}" \
    --box 139.995 140.044 35.48 35.52 \
    --out docs/figures/tokyobay_depth_tp_chiba_channel_boso_box.png
#<--- jsasaki 2026-10-24
