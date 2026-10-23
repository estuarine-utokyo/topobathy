#!/bin/bash
# Inner Tokyo Bay depth maps from non-M7001 sources (Cabinet Office 2025, JCG 500 m,
# SRTM15+) in the style of docs/figures/tokyobay_inner_depth_tp.png -> docs/figures/.
#
#   pjsub scripts/genkai_plot_depth_sources.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=4
#PJM -L elapse=00:40:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
"${ENV}/bin/python" scripts/plot_depth_sources.py --out-dir docs/figures
