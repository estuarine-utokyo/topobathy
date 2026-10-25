#!/bin/bash
# Checks, compression and medium-size figures for the 10 m / 5 m DEMs (job 7176962 products).
#
#   pjsub -o logs/hires_dem_checks.%j.log scripts/genkai_hires_dem_checks.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=16
#PJM -L elapse=02:00:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export GMT_SESSION_NAME="hichk_${PJM_JOBID:-$$}"
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
PY="${ENV}/bin/python"
TP="${DATA_DIR}/geodata/bathymetry/M7001/TP"

echo "=== checks"; "${PY}" scripts/hires_dem_checks.py 2>&1 | grep -v -i warn

echo "=== compress the M7001-only 10 m DEM (written uncompressed by topobathy-m7001-dem)"
"${PY}" - "${TP}/M7001_dem_tokyobay_10m_m7001_only.nc" <<'PY'
import os, sys, xarray as xr
f = sys.argv[1]; tmp = f + ".zlib.tmp"
ds = xr.open_dataset(f); ds.load(); ds.close()
ds.to_netcdf(tmp, encoding={"elevation": {"zlib": True, "complevel": 4}})
a = xr.open_dataset(f)["elevation"].values; b = xr.open_dataset(tmp)["elevation"].values
import numpy as np
assert np.array_equal(np.isnan(a), np.isnan(b)) and np.nanmax(np.abs(a - b)) == 0
os.replace(tmp, f); print("compressed", f, os.path.getsize(f))
PY

echo "=== figures"
"${PY}" scripts/plot_dem_compare.py --before "${TP}/M7001_dem_tokyobay_50m.nc" \
    --after "${TP}/M7001_dem_tokyobay_10m.nc" --labels "50 m DEM" "10 m DEM" \
    --region 139.94 140.12 35.52 35.62 --vmax 20 --step 1 --dlim 3 --dpi 110 \
    --out docs/figures/chiba_channel_50m_vs_10m.png
"${PY}" scripts/plot_dem_compare.py --before "${TP}/M7001_dem_tokyobay_50m.nc" \
    --after "${TP}/M7001_dem_futtsu_5m.nc" --labels "50 m DEM" "5 m Futtsu DEM" \
    --region 139.770 139.830 35.300 35.340 --vmax 6 --step 0.5 --dlim 1.5 \
    --box 139.782 139.8195 35.3130 35.3305 --dpi 110 \
    --out docs/figures/futtsu_50m_vs_5m.png
"${PY}" scripts/plot_depth_map.py --dem "${TP}/M7001_dem_tokyobay_10m.nc" \
    --region 139.60 140.15 35.20 35.72 --vmax 30 --no-title --no-note --font-size 14 \
    --cbar-label "Depth (m)" --dpi 150 --out docs/figures/tokyobay_depth_tp_10m.png
echo "=== done"
