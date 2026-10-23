#!/bin/bash
# Endo (2020) 50 m grid: A.P. -> T.P., checked against M7001 on flat seabed.
#
#   pjsub -o logs/endo50m_to_tp.%j.log scripts/genkai_endo50m_to_tp.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=2
#PJM -L elapse=00:15:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
D="${DATA_DIR}/geodata/bathymetry/tokyobay_endo/nc"
"${ENV}/bin/python" scripts/endo50m_to_tp.py --src "${D}/endo_50m_lonlat.nc" --out "${D}/endo_50m_lonlat_tp.nc"
