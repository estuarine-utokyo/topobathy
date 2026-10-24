#!/bin/bash
# Merge the Fisheries Agency 2022 Futtsu survey (0.5 m, T.P.) into the 50 m Tokyo Bay DEM
# (M7001 + Chiba channel). Writes the merged DEM to OUT (default: a staging name, so the
# result can be checked before it takes the default file name) and a difference map.
#
#   pjsub -o logs/futtsu_jfa_merge.%j.log scripts/genkai_futtsu_jfa_merge.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=4
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
BASE="${BASE:-${TP}/M7001_dem_tokyobay_50m_chiba_channel.nc}"
OUT="${OUT:-${TP}/M7001_dem_tokyobay_50m_futtsu_staging.nc}"
"${ENV}/bin/python" scripts/futtsu_jfa_merge.py --base "${BASE}" --out "${OUT}" \
    --diff-png docs/figures/futtsu_merge_diff.png
