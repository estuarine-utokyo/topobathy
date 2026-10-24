#!/bin/bash
# Futtsu close-up before / after merging the Fisheries Agency 2022 survey (0.5 m colour
# steps to 6 m), to check the merge.
#
#   pjsub -x BEFORE=...,AFTER=... -o logs/plot_futtsu_merge.%j.log scripts/genkai_plot_futtsu_merge.sh
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
BEFORE="${BEFORE:-${TP}/M7001_dem_tokyobay_50m_chiba_channel.nc}"
AFTER="${AFTER:-${TP}/M7001_dem_tokyobay_50m.nc}"
for pair in "before:${BEFORE}" "after:${AFTER}"; do
    tag="${pair%%:*}"; dem="${pair#*:}"
    "${ENV}/bin/python" scripts/plot_depth_map.py --dem "${dem}" \
        --region 139.770 139.830 35.300 35.340 --vmax 6 --fine-to 6 --fine-step 0.5 \
        --contour 1 --fill-gaps --scalebar 1 --box 139.782 139.819 35.3135 35.330 \
        --no-title --no-note --font-size 14 --cbar-label "Depth (m)" \
        --out "docs/figures/futtsu_merge_${tag}.png"
done
