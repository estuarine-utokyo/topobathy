#!/bin/bash
# Tokyo Bay depth map (T.P., M7001 with the Chiba channel corrected, south to 35.2 N)
# with the seabed mounds of the Boso close-up criteria circled: summit 7-14 m, >= 1 m
# above the surrounding seabed, <= 2 km from shore, mean slope of the upper half >= 1:50.
# Excluded: Umi-hotaru (Tokyo Bay Aqua-Line artificial island, 139.871 E 35.464 N; box
# 139.862-139.880 E, 35.460-35.472 N) -- an artificial structure, not a seabed mound;
# and mounds with a charted rock point (海しる) within 300 m of the top, i.e. rocky
# ground such as the Miura shore, since the aim is sandy mound tops in a muddy seabed.
#
#   pjsub -o logs/plot_tokyobay_mounds.%j.log scripts/genkai_plot_tokyobay_mounds.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=2
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
"${ENV}/bin/python" scripts/plot_depth_map.py \
    --dem "${DATA_DIR}/geodata/bathymetry/M7001/TP/M7001_dem_tokyobay_50m_chiba_channel.nc" \
    --region 139.60 140.15 35.20 35.72 --vmax 30 \
    --mounds --mound-depth 7 14 --mound-prominence 1 --mound-shore-dist 2000 --mound-min-slope 0.02 \
    --mound-exclude-box 139.862 139.880 35.460 35.472 \
    --mound-exclude-points "${DATA_DIR}/sediment/substrate/msil_chart_substrate_points.csv" \
    --mound-exclude-classes rock --mound-exclude-radius 300 \
    --mound-csv docs/figures/tokyobay_mounds.csv \
    --no-title --no-note --font-size 14 --cbar-label "Depth (m)" \
    --out docs/figures/tokyobay_depth_tp_chiba_channel_mounds.png
