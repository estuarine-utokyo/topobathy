#!/bin/bash
# Rigorous M7001 chart-datum -> T.P. pipeline (Japan Coast Guard ERS method):
# TIN (linear) interpolation of the 85-station JMA/JCG datum table -> the whole-sheet
# point dataset and the continuous 最低水面モデル grid, written to
# $DATA_DIR/bathymetry/M7001/TP/. See docs/vertical_datum.md.
#
# Light single-thread NumPy job (parse ~3.95 M fixed-width records + TIN + I/O).
# Runs on the GENKAI shared sub-node pool; if the estimated start (pjstat
# START_DATE) exceeds 24 h, pjdel and resubmit as `#PJM -L node=1`.
#
#   pjsub scripts/genkai_m7001_to_tp.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=4
#PJM -L elapse=00:25:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"

PY="${HOME}/mambaforge/envs/topobathy/bin/python"
cd "${HOME}/Github/topobathy"
TP="${DATA_DIR}/bathymetry/M7001/TP"

# Rigorous interpolation = linear (TIN), the JCG ERS method. Override e.g. METHOD=idw.
METHOD="${METHOD:-linear}"
KS_BBOX="138.20 141.60 33.10 36.00"          # whole Kanto-South extent

# GSI geoid (「日本のジオイド2011」) for the ellipsoidal-height branch; download it
# once with scripts/get_gsigeo.py. If absent, the products are T.P.-only (the T.P.
# conversion never needs the geoid).
GEOID_ASC="$(ls "${DATA_DIR}"/geoid/gsigeo2011*.asc 2>/dev/null | sort -r | head -1 || true)"
[ -n "${GEOID_ASC}" ] && echo "geoid: ${GEOID_ASC}" || echo "geoid: (none; T.P.-only products)"
CONV_GEOID=(); [ -n "${GEOID_ASC}" ] && CONV_GEOID=(--geoid "${GEOID_ASC}")

# --- point dataset (whole sheet; M7001 depths -> T.P., + z_ell if geoid) -----
# The whole-sheet product is the single source of truth; a Tokyo-Bay-only subset
# is just its bounding-box filter (identical values), so it is not written here.
"${PY}" -m topobathy.cli.m7001_to_tp --method "${METHOD}" --formats csv parquet \
    "${CONV_GEOID[@]}"

# --- continuous chart-datum model grid (最低水面モデル, JCG 1′×1.5′;
#     + chart_datum_ellipsoidal 最低水面の楕円体高 if geoid) ------------------
# shellcheck disable=SC2086
"${PY}" -m topobathy.cli.build_datum_model --method "${METHOD}" --bbox ${KS_BBOX} \
    "${CONV_GEOID[@]}" --out "${TP}/M7001_chart_datum_model_kanto_south.nc"

echo "done."
