#!/bin/bash
# 10 m Tokyo Bay T.P. DEM (window of the 50 m DEM) and the nested 5 m Futtsu DEM, from the
# original data (docs/dem_hires_plan.md):
#   1. M7001 soundings -> 0.0001 deg DEM (GMT surface, tension 0.35, 2 km mask, OSM land)
#   2. Chiba channel: harmonic refill of the flats + straight channel, side slope 1:10
#   3. Futtsu 2022 survey merged at 0.0001 deg (100 m edge ramp)       -> default 10 m name
#   4. 5 m base over 139.77-139.83 E, 35.30-35.34 N, nested in the 10 m lattice
#   5. Futtsu 2022 survey merged at 0.00005 deg (50 m edge ramp)       -> Futtsu 5 m DEM
#
#   pjsub -o logs/dem_10m_futtsu_5m.%j.log scripts/genkai_dem_10m_futtsu_5m.sh
#   (STAGES="3 4 5" to rerun from a stage)
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=16
#PJM -L elapse=04:00:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export GMT_SESSION_NAME="dem10_${PJM_JOBID:-$$}"
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
PY="${ENV}/bin/python"
TP="${DATA_DIR}/geodata/bathymetry/M7001/TP"
STAGES="${STAGES:-1 2 3 4 5}"
B10="${TP}/M7001_dem_tokyobay_10m_m7001_only.nc"
C10="${TP}/M7001_dem_tokyobay_10m_chiba_channel.nc"
F10="${TP}/M7001_dem_tokyobay_10m.nc"
B5="${TP}/M7001_dem_futtsu_5m_base.nc"
F5="${TP}/M7001_dem_futtsu_5m.nc"
run() { echo "=== stage $1 $(date '+%F %T')"; }

if [[ " ${STAGES} " == *" 1 "* ]]; then run 1
  "${PY}" -m topobathy.cli.m7001_dem --region 139.50 140.35 34.85 35.80 --spacing 0.0001 \
      --tension 0.35 --mask-km 2.0 --out "${B10}"
fi
if [[ " ${STAGES} " == *" 2 "* ]]; then run 2
  "${PY}" scripts/m7001_chiba_channel.py --m7001 "${B10}" --side-slope 0.1 --out "${C10}"
fi
if [[ " ${STAGES} " == *" 3 "* ]]; then run 3
  "${PY}" scripts/futtsu_jfa_merge.py --base "${C10}" --ramp 100 --out "${F10}" \
      --diff-png docs/figures/futtsu_merge_diff_10m.png
fi
if [[ " ${STAGES} " == *" 4 "* ]]; then run 4
  "${PY}" scripts/refine_dem_subset.py --dem "${F10}" --region 139.77 139.83 35.30 35.34 \
      --spacing 0.00005 --out "${B5}"
fi
if [[ " ${STAGES} " == *" 5 "* ]]; then run 5
  "${PY}" scripts/futtsu_jfa_merge.py --base "${B5}" --ramp 50 --out "${F5}" \
      --diff-png docs/figures/futtsu_merge_diff_5m.png
fi
echo "=== done $(date '+%F %T')"; ls -la "${TP}"/M7001_dem_tokyobay_10m*.nc "${TP}"/M7001_dem_futtsu_5m*.nc
