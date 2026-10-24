#!/usr/bin/env python3
"""Side-by-side close-up of two DEMs and their difference (before | after | after - before).

Depth panels use the same cmocean colours and steps; the difference panel is diverging,
symmetric about zero (negative = deeper after). OSM land via xcoast on every panel.

    python scripts/plot_dem_compare.py --before A.nc --after B.nc \
        --region 139.770 139.830 35.300 35.340 --vmax 6 --step 0.5 --out docs/figures/x.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from topobathy.plot.depthmap import land_mask


def load(path: Path, region) -> xr.DataArray:
    w, e, s, n = region
    da = xr.open_dataset(path)["elevation"].sortby("lat").sortby("lon")
    return da.sel(lon=slice(w, e), lat=slice(s, n)).astype("float64")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--labels", nargs=2, default=("Before", "After"))
    ap.add_argument("--region", type=float, nargs=4, metavar=("W", "E", "S", "N"), required=True)
    ap.add_argument("--vmax", type=float, default=6.0)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--dlim", type=float, default=None, help="difference colour limit (m)")
    ap.add_argument("--box", type=float, nargs=4, default=None, metavar=("W", "E", "S", "N"))
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import cmocean
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import MaxNLocator

    w, e, s, n = args.region
    a = load(args.before, args.region)
    b = load(args.after, args.region)
    diff = (b - a).where(np.abs(b - a) > 1e-4)
    lim = args.dlim or float(np.ceil(np.nanpercentile(np.abs(diff), 98) * 2) / 2)
    levels = np.arange(0.0, args.vmax + args.step / 2, args.step)
    dlev = np.linspace(-lim, lim, 13)
    land = land_mask(args.region)
    aspect = 1.0 / np.cos(np.radians((s + n) / 2))

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.9), constrained_layout=True)
    for ax, da, title in ((axes[0], a, args.labels[0]), (axes[1], b, args.labels[1])):
        cf = ax.contourf(da.lon, da.lat, (-da).clip(min=0), levels=levels, cmap=cmocean.cm.deep,
                         extend="max")
        ax.set_title(title, loc="left", fontsize=12)
    cd = axes[2].contourf(diff.lon, diff.lat, diff, levels=dlev, cmap="RdBu", extend="both")
    axes[2].set_title("Change (after − before)", loc="left", fontsize=12)
    for ax in axes:
        land.add_to_plain_mpl(ax, facecolor="#d9d6cf", edgecolor="#4a4a4a", linewidth=0.5,
                              zorder=5)
        if args.box:
            bw, be, bs, bn = args.box
            ax.add_patch(Rectangle((bw, bs), be - bw, bn - bs, fill=False, edgecolor="#d62728",
                                   linewidth=1.2, zorder=10))
        ax.set_xlim(w, e)
        ax.set_ylim(s, n)
        ax.set_aspect(aspect)
        ax.ticklabel_format(useOffset=False, style="plain")
        ax.tick_params(labelsize=9)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.set_xlabel("Longitude (°E)", fontsize=10)
    axes[0].set_ylabel("Latitude (°N)", fontsize=10)
    for ax in axes[1:]:
        ax.set_yticklabels([])
    cb = fig.colorbar(cf, ax=axes[:2], shrink=0.85, pad=0.01,
                      ticks=np.arange(0, args.vmax + 0.1, 1))
    cb.set_label("Depth (m)", fontsize=10)
    cb.ax.invert_yaxis()
    cb2 = fig.colorbar(cd, ax=axes[2], shrink=0.85, pad=0.02)
    cb2.set_label("Elevation change (m)\n(negative = deeper)", fontsize=10)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi)
    print(f"wrote {args.out}; changed cells {int(np.isfinite(diff).sum())}, "
          f"change {np.nanmin(diff):+.2f} to {np.nanmax(diff):+.2f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
