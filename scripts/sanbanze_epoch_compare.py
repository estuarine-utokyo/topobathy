#!/usr/bin/env python3
"""Compare the Sanbanze 10 m surveys between epochs on flat seabed (A.P., no datum shift).

All epochs share one 10 m lattice (origin 7686.7 / -40674.2 in the files), so the same node is
compared directly. A node is "flat" when the slope in the OLDER epoch is < --slope, with depth
between --zmin and --zmax (A.P.). Prints, per pair, the median / IQR of (newer - older) and n,
and the median per 1 km northing band for the pairs across the 2011 earthquake.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from topobathy import config

ORDER = ["S55", "S61", "H03", "H12", "H14", "H20", "H24", "H28"]


def load(src: Path, ep: str) -> pd.DataFrame:
    t = pd.read_csv(src / f"10m{ep}JGD.csv", skipinitialspace=True, dtype=np.float64)
    t.columns = [c.strip() for c in t.columns]
    t = t[t.Z < 9000]
    t["ix"] = np.rint((t.X - 7686.7) / 10).astype(int)
    t["iy"] = np.rint((t.Y + 40674.2) / 10).astype(int)
    return t


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=config.get_bathymetry_dir() / "tokyo_bay"
                    / "Sanbanze_Chiba_AP" / "csv")
    ap.add_argument("--slope", type=float, default=0.01)
    ap.add_argument("--zmin", type=float, default=-10.0)
    ap.add_argument("--zmax", type=float, default=-1.5)
    args = ap.parse_args()
    ep = {e: load(args.src, e) for e in ORDER}
    nx = max(int(t.ix.max()) for t in ep.values()) + 1
    ny = max(int(t.iy.max()) for t in ep.values()) + 1
    grid = {}
    for e, t in ep.items():
        g = np.full((ny, nx), np.nan)
        g[t.iy.values, t.ix.values] = t.Z.values
        grid[e] = g

    def flat_diff(a: str, b: str):
        ga, gb = grid[a], grid[b]
        gy, gx = np.gradient(np.where(np.isfinite(ga), ga, np.nan), 10.0)
        sl = np.hypot(gx, gy)
        m = np.isfinite(ga) & np.isfinite(gb) & (sl < args.slope) & (ga > args.zmin) & (ga < args.zmax)
        return (gb - ga), m

    print(f"{'pair':10s} {'n':>7s} {'median':>8s} {'IQR':>16s}   (newer - older, m, A.P.)")
    pairs = [("S55", "S61"), ("S61", "H03"), ("H03", "H12"), ("H12", "H14"), ("H14", "H20"),
             ("H20", "H24"), ("H24", "H28"), ("H20", "H28"), ("H14", "H24"), ("H12", "H20")]
    for a, b in pairs:
        d, m = flat_diff(a, b)
        v = d[m]
        if v.size:
            print(f"{a}->{b:4s} {v.size:7d} {np.median(v):+8.3f} "
                  f"{np.percentile(v, 25):+7.2f} .. {np.percentile(v, 75):+6.2f}")
    print("\nacross the 2011 earthquake (H20 -> H24): median by 1 km northing band")
    d, m = flat_diff("H20", "H24")
    iy = np.nonzero(m)[0]
    north = -40674.2 + iy * 10.0
    v = d[m]
    for lo in np.arange(-40700, -35000, 1000):
        s = (north >= lo) & (north < lo + 1000)
        if s.sum() > 200:
            print(f"  northing {lo/1000:6.1f} .. {(lo+1000)/1000:6.1f} km  n={s.sum():6d}  median {np.median(v[s]):+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
