#!/usr/bin/env python3
"""Cut a sub-window out of a DEM onto a finer, nested lattice (the base of a nested DEM).

The output lattice starts at the window's W/S edge with step ``--spacing``; when that
step divides the parent's step and the window edges are parent nodes, every parent node
is also an output node (nested grids). Values are the parent's, bilinearly interpolated;
water cells left NaN next to the coast by the interpolation are filled from the nearest
water value, and land is then masked again at the finer spacing from the OSM coastline
(xcoast), exactly as the parent was hydro-flattened. This file is only the BASE onto which
finer data (e.g. a 0.5 m survey) are merged; on its own it carries no new information.

    python scripts/refine_dem_subset.py --dem .../M7001_dem_tokyobay_10m.nc \
        --region 139.77 139.83 35.30 35.34 --spacing 0.00005 --out base_5m.nc
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.ndimage import distance_transform_edt

from topobathy.grid import osm_land_geometry
from topobathy.grid.dem import _on_land


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dem", type=Path, required=True)
    ap.add_argument("--region", type=float, nargs=4, metavar=("W", "E", "S", "N"), required=True)
    ap.add_argument("--spacing", type=float, required=True, help="deg")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    w, e, s, n = args.region
    d = args.spacing
    lon = np.round(w + d * np.arange(int(round((e - w) / d)) + 1), 8)
    lat = np.round(s + d * np.arange(int(round((n - s) / d)) + 1), 8)
    src = xr.open_dataset(args.dem)
    par = src["elevation"].astype("float64")
    pd_ = float(np.median(np.diff(par.lon.values)))
    pad = 3 * pd_
    par = par.sel(lon=slice(w - pad, e + pad), lat=slice(s - pad, n + pad))
    fine = par.interp(lon=lon, lat=lat, method="linear")
    v = fine.values
    # fill NaN from the nearest finite value, then re-mask land at the fine spacing
    _, (iy, ix) = distance_transform_edt(~np.isfinite(v), return_indices=True)
    v = v[iy, ix]
    fine = fine.copy(data=v)
    land = _on_land(fine, osm_land_geometry((w, e, s, n)))
    fine = fine.where(~land)
    out = xr.Dataset({"elevation": fine.astype("float32")})
    out["elevation"].attrs = dict(src["elevation"].attrs)
    out["lon"].attrs = {"units": "degrees_east", "standard_name": "longitude"}
    out["lat"].attrs = {"units": "degrees_north", "standard_name": "latitude"}
    out.attrs = {
        "title": f"{args.dem.name} refined to {d:g} deg over {w}-{e} E, {s}-{n} N (base only)",
        "refine": (f"bilinear from {args.dem.name} (spacing {pd_:g} deg) onto a nested "
                   f"{d:g} deg lattice; NaN filled from the nearest water value; land re-masked "
                   "from the OSM coastline (xcoast) at the fine spacing"),
        "history": f"scripts/refine_dem_subset.py (topobathy) from {args.dem}",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(args.out, encoding={"elevation": {"zlib": True, "complevel": 4}})
    nested = np.isclose((par.lon.values[:, None] - lon[None, :]), 0, atol=1e-9).any(axis=1).sum()
    print(f"wrote {args.out}: {lat.size} x {lon.size}, water {int(np.isfinite(fine.values).sum())}; "
          f"parent lon nodes on the fine lattice: {nested}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
