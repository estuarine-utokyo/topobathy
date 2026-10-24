#!/bin/bash
# Futtsu close-up: DEM before | after the Futtsu merge | difference, medium PNG.
#
#   pjsub -o logs/plot_futtsu_compare.%j.log scripts/genkai_plot_futtsu_compare.sh
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
TP="${DATA_DIR}/geodata/bathymetry/M7001/TP"
"${ENV}/bin/python" scripts/plot_dem_compare.py \
    --before "${TP}/M7001_dem_tokyobay_50m_chiba_channel.nc" --after "${TP}/M7001_dem_tokyobay_50m.nc" \
    --labels "Before" "After (Futtsu survey merged)" \
    --region 139.770 139.830 35.300 35.340 --vmax 6 --step 0.5 --dlim 1.5 \
    --box 139.782 139.819 35.3135 35.330 --dpi 110 \
    --out docs/figures/futtsu_merge_compare.png
