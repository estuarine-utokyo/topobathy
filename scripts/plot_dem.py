#!/usr/bin/env python3
"""Render a filled-contour figure of a topobathy DEM NetCDF (smooth, tension-spline).

python scripts/plot_dem.py <dem.nc> <out.png>
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("usage: plot_dem.py <dem.nc> <out.png>")
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    da = xr.open_dataset(src)["elevation"]
    depth = -da  # plot depth below T.P. (positive down), like the other maps

    levels = np.array(
        [0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 800],
        dtype=float,
    )
    dmax = float(np.nanmax(depth.values))
    levels = levels[: int(np.searchsorted(levels, dmax)) + 1]

    fig, ax = plt.subplots(figsize=(8.2, 8.0))
    cf = ax.contourf(
        da["lon"], da["lat"], depth, levels=levels, cmap="turbo", extend="max"
    )
    ax.contour(
        da["lon"],
        da["lat"],
        depth,
        levels=levels,
        colors="k",
        linewidths=0.3,
        alpha=0.35,
    )
    ax.set_aspect(1.0 / np.cos(np.radians(float(da["lat"].mean()))))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("M7001 DEM — depth below T.P. (GMT surface, splines in tension)")
    fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.02).set_label("depth below T.P. (m)")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
