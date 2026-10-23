#!/bin/bash
# Inner Tokyo Bay depth map from the Endo (2020) 50 m grid: regrid the water points to
# lon/lat NetCDF beside the source, then plot in the M7001 map style, cropped to the
# extent of the data inside the usual frame (139.60-140.15 E, 35.36-35.72 N).
#
#   pjsub -o logs/plot_inner_bay_depth_endo50m.%j.log scripts/genkai_plot_inner_bay_depth_endo50m.sh
#
#PJM -L rscgrp=a-batch
#PJM -L vnode=1
#PJM -L vnode-core=2
#PJM -L elapse=00:20:00
#PJM -j
#PJM -X
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
: "${DATA_DIR:?DATA_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
: "${WORK_DIR:?WORK_DIR unset (need '#PJM -X' so the login-shell env is passed)}"
ENV="${WORK_DIR}/mambaforge/envs/topobathy"
export PROJ_DATA="${ENV}/share/proj" GDAL_DATA="${ENV}/share/gdal"
cd "${WORK_DIR}/Github/topobathy"
NC="${DATA_DIR}/geodata/bathymetry/tokyobay_endo/nc/endo_50m_lonlat.nc"
"${ENV}/bin/python" scripts/endo50m_to_lonlat.py --out "${NC}"
# frame = data extent clipped to the usual inner-bay frame
read -r W E S N < <("${ENV}/bin/python" - "${NC}" <<'PY'
import sys, numpy as np, xarray as xr
z = xr.open_dataset(sys.argv[1])["elevation"]
ok = np.isfinite(z)
lon = z.lon[ok.any("lat")]; lat = z.lat[ok.any("lon")]
print(max(139.60, round(float(lon.min()), 3)), min(140.15, round(float(lon.max()), 3)),
      max(35.36, round(float(lat.min()) + 0.001, 3)), min(35.72, round(float(lat.max()), 3)))
PY
)
echo "frame: ${W} ${E} ${S} ${N}"
"${ENV}/bin/python" scripts/plot_depth_map.py \
    --dem "${NC}" --region "${W}" "${E}" "${S}" "${N}" --vmax 30 --cmap deep \
    --title "Inner Tokyo Bay: depth, 50 m grid (Endo 2020)" \
    --cbar-label "Depth (m), datum not stated" \
    --source-note "Source: earlier 50 m Tokyo Bay data, aligned to the GSI coastline and merged with the Sanbanze FY2011 survey (Chiba Pref.) by M. Endo, 2020; land: OpenStreetMap via xcoast." \
    --out docs/figures/tokyobay_inner_depth_endo50m.png
