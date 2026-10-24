#!/bin/bash
# Close-up of the Boso shore (Ichihara / Sodegaura), 35.48-35.52 N, about 4.4 km square,
# from M7001 with the Chiba channel corrected; colours to 20 m in 1 m steps; mounds
# (summit 7-14 m, >= 1 m above the surrounding seabed, <= 2 km from shore, mean slope of
# the upper half >= 0.02 = 1:50, no charted rock point within 300 m) circled.
#
#   pjsub -o logs/plot_boso_zoom.%j.log scripts/genkai_plot_boso_zoom.sh
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
    --dem "${DATA_DIR}/geodata/bathymetry/M7001/TP/M7001_dem_tokyobay_50m_chiba_channel.nc" \
    --region 139.995 140.044 35.48 35.52 --vmax 20 --fine-to 20 --fill-gaps --scalebar 1 \
    --mounds --mound-depth 7 14 --mound-prominence 1 --mound-shore-dist 2000 --mound-min-slope 0.02 \
    --mound-exclude-points "${DATA_DIR}/sediment/substrate/msil_chart_substrate_points.csv" \
    --mound-exclude-classes rock --mound-exclude-radius 300 \
    --mound-csv docs/figures/boso_ichihara_mounds.csv \
    --no-title --no-note --font-size 14 --cbar-label "Depth (m)" \
    --out docs/figures/boso_ichihara_zoom_depth.png
