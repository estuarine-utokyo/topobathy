#!/bin/bash
# ARCHIVE-GRADE M7001 DEM: 0.0005 deg (~45 x 55 m) over the FULL M7001 archive
# extent (owner 2026-08-09: "水深データの範囲はM7001と同一"). The existing
# 0.002 deg (~181 x 222 m) DEM was a sample built while developing the T.P.
# conversion and is too coarse to be permanent -- at that spacing the dredged
# channels off Sanbanze (250-300 m wide) span only 1-2 cells. This product is
# co-registered with the Tokyo Bay water-content dataset (same 0.0005 deg
# node lattice): sediment/docs/water_content_dataset.md.
#
# Grid: 137.90-141.60 E x 33.40-35.90 N -> 7401 x 5001 = 37.0 M cells.
#
#   pjsub scripts/genkai_m7001_dem_50m.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=16
#PJM -L elapse=03:00:00
#PJM -j
#PJM -X
#PJM -N m7001-dem50
#PJM -o logs/m7001_dem_50m_%j.log
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export GMT_SESSION_NAME="dem50_${PJM_JOBID:-$$}"
export PROJ_DATA="${HOME}/mambaforge/envs/topobathy/share/proj"
export GDAL_DATA="${HOME}/mambaforge/envs/topobathy/share/gdal"

: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X')}"

PY="${HOME}/mambaforge/envs/topobathy/bin/python"
cd "${HOME}/Github/topobathy"
mkdir -p logs
TP="${DATA_DIR}/geodata/bathymetry/M7001/TP"

"${PY}" -m topobathy.cli.m7001_dem \
    --region 137.90 141.60 33.40 35.90 --spacing 0.0005 --tension 0.35 \
    --mask-km 2.0 \
    --out "${TP}/M7001_dem_kanto_south_50m.nc"

echo "done."
