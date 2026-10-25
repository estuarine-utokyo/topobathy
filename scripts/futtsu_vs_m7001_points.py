#!/usr/bin/env python3
"""Compare the Futtsu 2022 survey (raw 0.5 m nodes, T.P.) with the M7001 soundings (T.P.).

Only M7001 points with survey nodes within ``--radius`` m are compared (median of those
nodes minus the M7001 elevation), so the comparison is confined to where the survey
actually is. Reported overall, by mark (N depth contours, M low-tide line) and by depth.

    python scripts/futtsu_vs_m7001_points.py
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

from topobathy import config


def stats(v: np.ndarray) -> str:
    if v.size == 0:
        return "n=0"
    q = np.percentile(v, [5, 25, 50, 75, 95])
    return (f"n={v.size} median {q[2]:+.3f} (IQR {q[1]:+.2f} to {q[3]:+.2f}, 5-95 % "
            f"{q[0]:+.2f} to {q[4]:+.2f}) m")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--radius", type=float, default=2.0)
    args = ap.parse_args()
    b = config.get_bathymetry_dir()
    tiles = sorted((b / "Futtsu_JFA_2023" / "05MCSV_TP").glob("*.txt"))
    sv = pd.concat([pd.read_csv(f, header=None, names=["id", "e", "n", "z", "flag"],
                                usecols=["e", "n", "z"]) for f in tiles], ignore_index=True)
    sv = sv[sv.z > -9000]
    tree = cKDTree(np.c_[sv.e.values, sv.n.values])
    pts = pd.read_parquet(b / "M7001" / "TP" / "M7001_TP.parquet", columns=["mark", "lon", "lat", "z_tp"])
    pts = pts[pts.mark.isin(["N", "M"]) & pts.lon.between(139.77, 139.83) & pts.lat.between(35.30, 35.34)]
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True).transform(
        pts.lon.values, pts.lat.values)
    near = tree.query_ball_point(np.c_[x, y], r=args.radius)
    zs = np.array([np.median(sv.z.values[i]) if len(i) else np.nan for i in near])
    ok = np.isfinite(zs)
    d = zs[ok] - pts.z_tp.values[ok]
    mk = pts.mark.values[ok]
    dep = -pts.z_tp.values[ok]
    print(f"survey nodes {len(sv)}; M7001 points near Futtsu {len(pts)}, with survey within "
          f"{args.radius:g} m: {ok.sum()}")
    print(f"survey - M7001 (elevation): {stats(d)}")
    for m in ("N", "M"):
        print(f"  mark {m}: {stats(d[mk == m])}")
    for lo, hi in ((-2, 0.5), (0.5, 1.5), (1.5, 2.5), (2.5, 10)):
        sel = (dep >= lo) & (dep < hi)
        print(f"  M7001 depth {lo}-{hi} m: {stats(d[sel])}")
    for m in ("N", "M"):
        z = pts.z_tp.values[ok][mk == m]
        if z.size:
            print(f"  mark {m} M7001 elevations: {np.unique(np.round(z, 2))[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
