#!/usr/bin/env python3
"""Depth map of a topobathy DEM over a sub-region, cmocean colours, xcoast land.

Depth = metres below T.P. (positive down) from the DEM variable ``elevation``.
Land is drawn from the OSM land polygons through xcoast (the same land mask used
for hydro-flattening the DEM, see docs/dem.md).

    python scripts/plot_depth_map.py --dem $DATA_DIR/geodata/bathymetry/M7001/TP/M7001_dem_tokyobay_50m.nc \
        --region 139.60 140.15 35.36 35.72 --vmax 30 --out docs/figures/tokyobay_inner_depth_tp.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cmocean  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402

from topobathy import config  # noqa: E402


def land_gdf(region: tuple[float, float, float, float]):
    """OSM true-land polygons over region (W, E, S, N), via xcoast."""
    import xcoast

    conf = xcoast.CoastmaskConfig(
        land_shp_path=config.osm_land_shp(),
        water_shp_path=config.osm_water_shp(),
        cache_dir=config.coastmask_cache_dir(),
        remove_orphan_islands=False,
    )
    w, e, s, n = region
    pad = 0.05  # load a little wider so polygons are not cut at the frame
    return xcoast.load((w - pad, s - pad, e + pad, n + pad), config=conf)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dem", type=Path, required=True)
    ap.add_argument("--region", type=float, nargs=4, metavar=("W", "E", "S", "N"),
                    required=True)
    ap.add_argument("--vmax", type=float, default=30.0, help="colour-bar maximum depth (m)")
    ap.add_argument("--step", type=float, default=2.0, help="colour step (m)")
    ap.add_argument("--contour", type=float, default=5.0, help="contour interval (m), 0 = none")
    ap.add_argument("--cmap", default="deep", help="cmocean colormap name")
    ap.add_argument("--title", default="Inner Tokyo Bay (north of Kisarazu): depth below T.P.")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    w, e, s, n = args.region
    da = xr.open_dataset(args.dem)["elevation"].sel(lon=slice(w, e), lat=slice(s, n))
    depth = -da
    levels = np.arange(0.0, args.vmax + args.step / 2, args.step)
    cmap = getattr(cmocean.cm, args.cmap)

    fig, ax = plt.subplots(figsize=(8.0, 6.4))
    cf = ax.contourf(da.lon, da.lat, depth.clip(min=0), levels=levels, cmap=cmap,
                     extend="max")
    if args.contour > 0:
        cl = np.arange(args.contour, args.vmax + 0.1, args.contour)
        cs = ax.contour(da.lon, da.lat, depth, levels=cl, colors="k", linewidths=0.4,
                        alpha=0.5)
        ax.clabel(cs, fmt="%g", fontsize=7, inline_spacing=2)
    land_gdf(args.region).add_to_plain_mpl(ax, facecolor="#d9d6cf", edgecolor="#4a4a4a",
                                           linewidth=0.5, zorder=5)
    ax.set_xlim(w, e)
    ax.set_ylim(s, n)
    ax.set_aspect(1.0 / np.cos(np.radians((s + n) / 2)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title(args.title, loc="left", fontsize=11)
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label("Depth below T.P. (m)")
    cb.ax.invert_yaxis()  # deeper downwards
    ax.text(0.01, -0.12, f"Source: M7001 (JHA) converted to T.P., GMT surface DEM "
            f"({args.dem.name}); land: OpenStreetMap via xcoast.",
            transform=ax.transAxes, fontsize=7, color="#52514e")
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    print(f"wrote {args.out}; depth range in region: "
          f"{float(np.nanmin(depth)):.1f} to {float(np.nanmax(depth)):.1f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
