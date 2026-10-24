#!/usr/bin/env python3
"""Feasibility of a 10 m / 5 m Tokyo Bay DEM on the 50 m DEM window: data density and cost.

1. M7001 point density in the window (139.50-140.35 E, 34.85-35.80 N): points per mark,
   nearest-neighbour spacing (percentiles), and the share of 10 m / 5 m cells that would
   hold a sounding, overall and in depth bands -- i.e. where a finer grid gets data of its
   own and where it only interpolates.
2. Pilot gridding with ``topobathy.grid.grid_dem`` (GMT blockmedian + surface + coverage
   mask + OSM hydro-flattening) on one 0.1 deg x 0.1 deg tile at 0.0001 deg (~10 m) and
   0.00005 deg (~5 m): wall time and peak memory, extrapolated to the window by area.

    python scripts/hires_dem_feasibility.py --tile 139.95 140.05 35.50 35.60
"""

from __future__ import annotations

import argparse
import resource
import time

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from topobathy import config

WIN = (139.50, 140.35, 34.85, 35.80)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tile", type=float, nargs=4, default=(139.95, 140.05, 35.50, 35.60))
    ap.add_argument("--spacings", type=float, nargs="+", default=(0.0001, 0.00005))
    args = ap.parse_args()

    w, e, s, n = WIN
    df = pd.read_parquet(config.get_bathymetry_dir() / "M7001" / "TP" / "M7001_TP.parquet",
                         columns=["mark", "lon", "lat", "z_tp"])
    df = df[(df.lon >= w) & (df.lon <= e) & (df.lat >= s) & (df.lat <= n)]
    print(f"M7001 points in window: {len(df)}; by mark: {df.mark.value_counts().to_dict()}")
    g = df[df.mark.isin(["N", "M"])]
    lat0 = np.radians((s + n) / 2)
    xy = np.c_[g.lon.values * 111_320 * np.cos(lat0), g.lat.values * 111_320]
    dist, _ = cKDTree(xy).query(xy, k=2)
    nn = dist[:, 1]
    print("nearest-neighbour spacing of N+M points (m): " +
          ", ".join(f"p{p} {np.percentile(nn, p):.1f}" for p in (5, 25, 50, 75, 95)))
    water_cells_50m = 1_320_734  # wet cells of the 50 m DEM (same window)
    for d, name in ((0.0001, "10 m"), (0.00005, "5 m")):
        ix = np.floor((g.lon.values - w) / d).astype(np.int64)
        iy = np.floor((g.lat.values - s) / d).astype(np.int64)
        occ = np.unique(iy * 10_000_000 + ix).size
        wet = water_cells_50m * (0.0005 / d) ** 2
        print(f"{name}: cells holding >= 1 point {occ} of ~{wet:.0f} wet cells "
              f"({100 * occ / wet:.2f} %)")
    depth = -g.z_tp.values
    for lo, hi in ((-5, 5), (5, 10), (10, 20), (20, 50), (50, 1e4)):
        sel = (depth >= lo) & (depth < hi)
        print(f"  depth {lo}-{hi:g} m: {sel.sum()} points, median NN spacing "
              f"{np.median(nn[sel]):.1f} m")

    # 2. pilot gridding
    from topobathy import grid_dem
    from topobathy.grid import osm_land_geometry
    tw, te, ts, tn = args.tile
    pad = 0.02
    sub = g[(g.lon >= tw - pad) & (g.lon <= te + pad) & (g.lat >= ts - pad) & (g.lat <= tn + pad)]
    land = osm_land_geometry((tw, te, ts, tn))
    area_ratio = ((e - w) * (n - s)) / ((te - tw) * (tn - ts))
    for d in args.spacings:
        t0 = time.time()
        dem = grid_dem(sub.lon.values, sub.lat.values, sub.z_tp.values, region=(tw, te, ts, tn),
                       spacing=d, tension=0.35, mask_km=2.0, land_geom=land)
        dt = time.time() - t0
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
        print(f"pilot {d:g} deg: grid {dem.shape}, {dt:.0f} s, peak RSS {rss:.1f} GB so far; "
              f"x{area_ratio:.0f} by area -> ~{dt * area_ratio / 3600:.1f} h serial for the window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
