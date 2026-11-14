#!/bin/bash
# Merge the MLIT Akanehama single-beam survey into the Sanbanze-merged 50 m and 10 m T.P. DEMs
# (staging files; check them, then give them the default names).
#   pjsub -o logs/akanehama_merge.%j.log scripts/genkai_akanehama_merge.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=4
#PJM -L elapse=00:30:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X')}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X')}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
TP="${DATA_DIR}/geodata/bathymetry/M7001/TP"
PTS="${DATA_DIR}/geodata/bathymetry/Akanehama_MLIT/processed/akanehama_sb_points.csv"
mkdir -p "$(dirname "${PTS}")"
"${ENV}/bin/python" scripts/akanehama_points.py --out "${PTS}"
for R in 50m 10m; do
  "${ENV}/bin/python" scripts/akanehama_merge.py \
      --base "${TP}/M7001_dem_tokyobay_${R}.nc" --points "${PTS}" \
      --out "${TP}/M7001_dem_tokyobay_${R}_akanehama_staging.nc" \
      --diff-png "docs/figures/akanehama_merge_diff_${R}.png"
done
