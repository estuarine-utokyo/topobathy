#!/bin/bash
# Render the three M7001 depth contour maps (chart datum, T.P., difference = Z0)
# into docs/figures/ from the T.P.-converted product.
#
# Light single-thread job (griddata over the Tokyo Bay N points + matplotlib).
#
#   pjsub scripts/genkai_plot_m7001_tp.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=4
#PJM -L elapse=00:15:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"

PY="${HOME}/mambaforge/envs/topobathy/bin/python"
cd "${HOME}/Github/topobathy"

# Default: Tokyo Bay product (Z0 physically valid) -> docs/figures/m7001_*.png
"${PY}" -m topobathy.cli.plot_m7001_tp --out-dir docs/figures --prefix m7001

echo "done."
