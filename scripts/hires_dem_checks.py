#!/usr/bin/env python3
"""Checks of the 10 m Tokyo Bay DEM and the 5 m Futtsu DEM.

1. Futtsu offset: inside the survey footprint, compare the survey (the 5 m Futtsu DEM,
   full-weight cells) with (a) the original M7001 soundings (N contours, M low-tide line,
   T.P.) at their own positions and (b) the 10 m M7001-only DEM. A uniform difference would
   be a datum offset; a difference that varies with depth or place is the M7001 spline
   misrepresenting the flats.
2. 10 m vs 50 m: the 10 m final DEM block-averaged onto the 50 m lattice (5 x 5 cells
   centred on each 50 m node) minus the 50 m final DEM, overall, on flat seabed, and in
   the Chiba channel corridor (side slope 1:10 at 10 m vs 1:25 at 50 m) and Futtsu.

    python scripts/hires_dem_checks.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from topobathy import config

FOOT = (139.782, 139.8195, 35.3130, 35.3305)


def stats(v: np.ndarray) -> str:
    v = v[np.isfinite(v)]
    if v.size == 0:
        return "n=0"
    q = np.percentile(v, [5, 25, 50, 75, 95])
    return (f"n={v.size} median {q[2]:+.3f} (IQR {q[1]:+.2f} to {q[3]:+.2f}, 5-95 % "
            f"{q[0]:+.2f} to {q[4]:+.2f}) m")


def main() -> int:
    tp = config.get_bathymetry_dir() / "M7001" / "TP"
    f5 = xr.open_dataset(tp / "M7001_dem_futtsu_5m.nc")["elevation"].astype("float64")
    b10 = xr.open_dataset(tp / "M7001_dem_tokyobay_10m_m7001_only.nc")["elevation"]
    w, e, s, n = FOOT

    # 1a. survey vs original M7001 soundings inside the footprint
    pts = pd.read_parquet(tp / "M7001_TP.parquet", columns=["mark", "lon", "lat", "z_tp"])
    pts = pts[pts.mark.isin(["N", "M"]) & (pts.lon >= w) & (pts.lon <= e) & (pts.lat >= s)
              & (pts.lat <= n)]
    sv = f5.interp(lon=xr.DataArray(pts.lon.values, dims="p"),
                   lat=xr.DataArray(pts.lat.values, dims="p"), method="nearest").values
    d = sv - pts.z_tp.values
    print(f"[futtsu] M7001 points in footprint: {len(pts)} ({pts.mark.value_counts().to_dict()})")
    print(f"[futtsu] survey - M7001 point (elevation): {stats(d)}")
    for lo, hi in ((-1, 0.5), (0.5, 1.5), (1.5, 2.5), (2.5, 5)):
        sel = (-pts.z_tp.values >= lo) & (-pts.z_tp.values < hi)
        print(f"[futtsu]   M7001 depth {lo}-{hi} m: {stats(d[sel])}")
    for mk in ("N", "M"):
        print(f"[futtsu]   mark {mk}: {stats(d[(pts.mark == mk).values])}")
    # 1b. survey vs the 10 m M7001-only DEM, cell by cell
    bsub = b10.sel(lon=slice(w, e), lat=slice(s, n)).astype("float64")
    fs = f5.interp(lon=bsub.lon, lat=bsub.lat, method="nearest")
    print(f"[futtsu] survey(5 m) - M7001-only DEM(10 m): {stats((fs - bsub).values.ravel())}")
    # by M7001 depth band of the DEM
    dd = (fs - bsub).values.ravel()
    z = -bsub.values.ravel()
    for lo, hi in ((-1, 0.5), (0.5, 1.5), (1.5, 2.5), (2.5, 5)):
        sel = (z >= lo) & (z < hi)
        print(f"[futtsu]   DEM depth {lo}-{hi} m: {stats(dd[sel])}")

    # 2. 10 m final block-averaged to 50 m vs 50 m final
    t10 = xr.open_dataset(tp / "M7001_dem_tokyobay_10m.nc")["elevation"].astype("float64")
    t50 = xr.open_dataset(tp / "M7001_dem_tokyobay_50m.nc")["elevation"].astype("float64")
    # the 50 m nodes are every 5th 10 m node: pad 2 cells, reshape to 5 x 5 blocks
    assert np.isclose(t10.lon.values[0], t50.lon.values[0]) and np.isclose(t10.lat.values[0], t50.lat.values[0])
    v = np.pad(t10.values.astype("float32"), 2, constant_values=np.nan)
    ny, nx = t50.shape
    v = v[: ny * 5, : nx * 5].reshape(ny, 5, nx, 5)
    cnt = np.isfinite(v).sum(axis=(1, 3))
    with np.errstate(invalid="ignore"):
        blk50 = np.where(cnt >= 13, np.nanmean(v, axis=(1, 3)), np.nan)
    del v
    diff = blk50 - t50.values
    gy, gx = np.gradient(np.nan_to_num(t50.values), 55.6, 45.3)
    flat = np.hypot(gx, gy) < 0.002
    LON, LAT = np.meshgrid(t50.lon.values, t50.lat.values)
    print(f"[10v50] all wet cells: {stats(diff.ravel())}")
    print(f"[10v50] flat seabed (slope < 0.002): {stats(diff[flat])}")
    print(f"[10v50] |diff| > 1 m: {int(np.nansum(np.abs(diff) > 1))} cells, > 3 m: "
          f"{int(np.nansum(np.abs(diff) > 3))}")
    chiba = (LON > 139.94) & (LON < 140.09) & (LAT > 35.52) & (LAT < 35.60)
    futt = (LON >= w) & (LON <= e) & (LAT >= s) & (LAT <= n)
    print(f"[10v50] Chiba channel box: {stats(diff[chiba])}")
    print(f"[10v50] Futtsu footprint: {stats(diff[futt])}")
    rest = ~chiba & ~futt
    print(f"[10v50] elsewhere: {stats(diff[rest])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
