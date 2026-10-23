#!/bin/bash
# M7001 50 m T.P. DEM with the Chiba channel corrected (smooth flats + Endo channel cut),
# then maps: whole inner bay (corrected) and a channel close-up before/after.
#
#   pjsub -o logs/m7001_chiba_channel.%j.log scripts/genkai_m7001_chiba_channel.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=2
#PJM -L elapse=00:30:00
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
OUT="${TP}/M7001_dem_tokyobay_50m_chiba_channel.nc"
PY="${ENV}/bin/python"
"${PY}" scripts/m7001_chiba_channel.py --out "${OUT}"
NOTE="Source: M7001 (JHA) converted to T.P., GMT surface DEM; Chiba channel from the Endo (2020) 50 m grid shifted to T.P.; land: OpenStreetMap via xcoast."
"${PY}" scripts/plot_depth_map.py --dem "${OUT}" --region 139.60 140.15 35.36 35.72 --vmax 30 \
    --title "Inner Tokyo Bay: depth below T.P., M7001 with Chiba channel corrected" \
    --source-note "${NOTE}" --out docs/figures/tokyobay_inner_depth_tp_chiba_channel.png
"${PY}" scripts/plot_depth_map.py --dem "${OUT}" --region 139.94 140.12 35.52 35.62 --vmax 30 \
    --title "Chiba channel: M7001 corrected" --source-note "${NOTE}" \
    --out docs/figures/chiba_channel_m7001_corrected.png
"${PY}" scripts/plot_depth_map.py --dem "${TP}/M7001_dem_tokyobay_50m.nc" \
    --region 139.94 140.12 35.52 35.62 --vmax 30 --title "Chiba channel: M7001 original" \
    --out docs/figures/chiba_channel_m7001_original.png
