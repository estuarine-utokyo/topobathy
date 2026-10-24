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
    # jsasaki 2026-10-23: owner asked for 1 m colour steps down to 10 m
    ap.add_argument("--fine-to", type=float, default=10.0,
                    help="use --fine-step colour steps from 0 m down to this depth")
    ap.add_argument("--fine-step", type=float, default=1.0, help="colour step above --fine-to (m)")
    ap.add_argument("--contour", type=float, default=5.0, help="contour interval (m), 0 = none")
    # jsasaki 2026-10-23: owner asked for contours without depth labels by default
    ap.add_argument("--contour-labels", action="store_true", help="label the contours")
    ap.add_argument("--cmap", default="deep", help="cmocean colormap name")
    ap.add_argument("--title", default="Inner Tokyo Bay (north of Kisarazu): depth below T.P.")
    ap.add_argument("--dpi", type=int, default=300)
    #---> jsasaki 2026-10-23: plot other grids (e.g. the 2020 CAO 30 m lat/lon copy, Band1)
    ap.add_argument("--var", default="elevation", help="elevation variable (+up)")
    ap.add_argument("--source-note", default=None, help="source line under the map")
    # jsasaki 2026-10-23: grids whose vertical datum is not T.P.
    ap.add_argument("--cbar-label", default="Depth below T.P. (m)")
    #---> jsasaki 2026-10-23: owner: maps without title / source line, larger labels
    ap.add_argument("--no-title", action="store_true", help="no title above the map")
    # jsasaki 2026-10-24: owner: colour range from a percentile of the depth in the frame
    # jsasaki 2026-10-24: display-only fill of the no-data sliver along the OSM coastline
    ap.add_argument("--fill-gaps", action="store_true",
                    help="fill NaN cells with the nearest value (plot only; land is drawn on top)")
    # jsasaki 2026-10-24: owner: outline of a zoom-in frame on the overview map
    ap.add_argument("--box", type=float, nargs=4, action="append", default=[],
                    metavar=("W", "E", "S", "N"), help="draw a rectangle (repeatable)")
    # jsasaki 2026-10-24: owner: scale bar in the lower-right corner
    ap.add_argument("--scalebar", type=float, default=None, metavar="KM",
                    help="draw a scale bar of this length (km) in the lower-right corner")
    #---> jsasaki 2026-10-24: owner: mark seabed mounds (topobathy.grid.mounds)
    ap.add_argument("--mounds", action="store_true", help="find and mark seabed mounds")
    ap.add_argument("--mound-depth", type=float, nargs=2, default=(7.0, 14.0),
                    metavar=("ZMIN", "ZMAX"), help="summit depth range (m)")
    ap.add_argument("--mound-prominence", type=float, default=1.0,
                    help="minimum rise above the surrounding seabed (m, topographic prominence)")
    ap.add_argument("--mound-shore-dist", type=float, default=2000.0,
                    help="maximum distance of the summit from land (m)")
    ap.add_argument("--mound-csv", type=Path, default=None, help="write the mounds found here")
    # jsasaki 2026-10-24: owner: steep mounds only (sandy tops in a muddy seabed)
    ap.add_argument("--mound-min-slope", type=float, default=0.0,
                    help="minimum mean flank slope = prominence / (base width / 2) (m/m)")
    ap.add_argument("--mound-width", type=float, nargs=2, default=None, metavar=("MIN", "MAX"),
                    help="base width range (m, equivalent-circle diameter)")
    #<--- jsasaki 2026-10-24
    ap.add_argument("--vmax-pct", type=float, default=None,
                    help="set --vmax to this percentile of the water depth in the frame (ceil, m)")
    ap.add_argument("--no-note", action="store_true", help="no source line under the map")
    ap.add_argument("--font-size", type=float, default=None,
                    help="axis/colour-bar label size (tick labels 1 pt smaller)")
    #<--- jsasaki 2026-10-23
    #<--- jsasaki 2026-10-23
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    w, e, s, n = args.region
    #---> jsasaki 2026-10-23: any variable name, either lat order, drop huge fill values
    da = xr.open_dataset(args.dem)[args.var].sortby("lat").sortby("lon")
    da = da.sel(lon=slice(w, e), lat=slice(s, n))
    da = da.where(np.abs(da) < 1.0e4)
    #<--- jsasaki 2026-10-23
    depth = -da
    #---> jsasaki 2026-10-24: --vmax-pct; colour-bar tick spacing follows vmax
    if args.vmax_pct is not None:
        wet = depth.values[np.isfinite(depth.values) & (depth.values > 0)]
        args.vmax = float(np.ceil(np.percentile(wet, args.vmax_pct)))
        print(f"vmax = {args.vmax:g} m ({args.vmax_pct:g}th percentile of {wet.size} wet cells, "
              f"max {wet.max():.2f} m)")
    tick_step = 5 if args.vmax >= 15 else (2 if args.vmax >= 6 else 1)
    #<--- jsasaki 2026-10-24
    #---> jsasaki 2026-10-24: --fill-gaps after --vmax-pct (nearest value; OSM land then covers real land)
    if args.fill_gaps:
        from scipy.ndimage import distance_transform_edt
        v = depth.values
        _, (iy, ix) = distance_transform_edt(~np.isfinite(v), return_indices=True)
        depth = depth.copy(data=v[iy, ix])
        da = -depth
    #<--- jsasaki 2026-10-24
    #---> jsasaki 2026-10-23: fine steps in the shallows, --step below
    levels = np.unique(np.concatenate([
        np.arange(0.0, args.fine_to, args.fine_step),
        np.arange(args.fine_to, args.vmax + args.step / 2, args.step)]))
    #<--- jsasaki 2026-10-23
    cmap = getattr(cmocean.cm, args.cmap)

    fig, ax = plt.subplots(figsize=(8.0, 6.4))
    cf = ax.contourf(da.lon, da.lat, depth.clip(min=0), levels=levels, cmap=cmap,
                     extend="max")
    if args.contour > 0:
        cl = np.arange(args.contour, args.vmax + 0.1, args.contour)
        cs = ax.contour(da.lon, da.lat, depth, levels=cl, colors="k", linewidths=0.4,
                        alpha=0.5)
        # jsasaki 2026-10-23: labels only on request
        if args.contour_labels:
            ax.clabel(cs, fmt="%g", fontsize=7, inline_spacing=2)
    land_gdf(args.region).add_to_plain_mpl(ax, facecolor="#d9d6cf", edgecolor="#4a4a4a",
                                           linewidth=0.5, zorder=5)
    #---> jsasaki 2026-10-24: --mounds on the raw grid, padded so shore distance and
    # prominence are not cut by the frame; only summits inside the frame are drawn
    if args.mounds:
        import csv
        from topobathy.grid.mounds import find_mounds
        pad_m = args.mound_shore_dist + 1000.0
        plat = pad_m / 111_320.0
        plon = pad_m / (111_320.0 * np.cos(np.radians((s + n) / 2)))
        big = xr.open_dataset(args.dem)[args.var].sortby("lat").sortby("lon")
        big = big.sel(lon=slice(w - plon, e + plon), lat=slice(s - plat, n + plat))
        big = big.where(np.abs(big) < 1.0e4)
        found = find_mounds(-big.values, big.lon.values, big.lat.values,
                            zmin=args.mound_depth[0], zmax=args.mound_depth[1],
                            min_prominence=args.mound_prominence,
                            max_shore_dist=args.mound_shore_dist,
                            # jsasaki 2026-10-24: slope and width filters
                            min_slope=args.mound_min_slope,
                            width_range=tuple(args.mound_width) if args.mound_width else None)
        found = [m for m in found if w <= m["lon"] <= e and s <= m["lat"] <= n]
        print(f"mounds: {len(found)} (summit {args.mound_depth[0]:g}-{args.mound_depth[1]:g} m, "
              f"prominence >= {args.mound_prominence:g} m, <= {args.mound_shore_dist:g} m from land, "
              # jsasaki 2026-10-24: report slope / width filters and values
              f"slope >= {args.mound_min_slope:g}, width {args.mound_width})")
        for m in found:
            print(f"  {m['lon']:.5f} E {m['lat']:.5f} N  depth {m['depth']:.2f} m  "
                  f"prominence {m['prominence']:.2f} m  width {m['width']:.0f} m  "
                  f"slope {m['slope']:.4f} (1:{1 / m['slope']:.0f})  shore {m['shore_dist']:.0f} m")
        if found:
            ax.scatter([m["lon"] for m in found], [m["lat"] for m in found], s=110,
                       facecolors="none", edgecolors="#d62728", linewidths=1.8, zorder=12)
        if args.mound_csv:
            args.mound_csv.parent.mkdir(parents=True, exist_ok=True)
            with open(args.mound_csv, "w", newline="") as f:
                # jsasaki 2026-10-24: + width, slope
                wr = csv.DictWriter(f, fieldnames=["lon", "lat", "depth", "prominence",
                                                   "width", "slope", "shore_dist"])
                wr.writeheader()
                for m in found:
                    wr.writerow({k: round(v, 5 if k in ("lon", "lat", "slope") else 2)
                                 for k, v in m.items()})
    #<--- jsasaki 2026-10-24
    #---> jsasaki 2026-10-24: --box rectangles above the land layer
    from matplotlib.patches import Rectangle
    for bw, be, bs, bn in args.box:
        ax.add_patch(Rectangle((bw, bs), be - bw, bn - bs, fill=False, edgecolor="#d62728",
                               linewidth=1.8, zorder=10))
    #<--- jsasaki 2026-10-24
    #---> jsasaki 2026-10-24: --scalebar (black/white bar, label above, lower right)
    if args.scalebar:
        km_per_deg = 111.32 * np.cos(np.radians((s + n) / 2))
        length = args.scalebar / km_per_deg
        x1 = e - 0.05 * (e - w)
        x0 = x1 - length
        y0 = s + 0.05 * (n - s)
        hgt = 0.012 * (n - s)
        half = length / 2
        for i, fc in enumerate(("black", "white")):
            ax.add_patch(Rectangle((x0 + i * half, y0), half, hgt, facecolor=fc,
                                   edgecolor="black", linewidth=1.0, zorder=11))
        fsz = (args.font_size or 10) - 1
        for xx, lab in ((x0, "0"), (x1, f"{args.scalebar:g} km")):
            ax.text(xx, y0 + hgt * 1.8, lab, ha="center", va="bottom", fontsize=fsz, zorder=11)
    #<--- jsasaki 2026-10-24
    ax.set_xlim(w, e)
    ax.set_ylim(s, n)
    ax.set_aspect(1.0 / np.cos(np.radians((s + n) / 2)))
    # jsasaki 2026-10-23: plain degrees on small frames (no "+1.4e2" offset)
    ax.ticklabel_format(useOffset=False, style="plain")
    #---> jsasaki 2026-10-23: optional title and label size
    fs = args.font_size
    ax.set_xlabel("Longitude (°E)", fontsize=fs)
    ax.set_ylabel("Latitude (°N)", fontsize=fs)
    if fs:
        ax.tick_params(labelsize=fs - 1)
    if not args.no_title:
        ax.set_title(args.title, loc="left", fontsize=11)
    #<--- jsasaki 2026-10-23
    # jsasaki 2026-10-23: keep the colour bar linear in depth with unequal steps
    # jsasaki 2026-10-23: colour bar as tall as the map, also for wide frames
    cax = ax.inset_axes([1.03, 0.0, 0.035, 1.0])
    cb = fig.colorbar(cf, cax=cax, spacing="proportional",
                      # jsasaki 2026-10-24: tick spacing from vmax
                      ticks=np.arange(0, args.vmax + 0.5, tick_step))
    # jsasaki 2026-10-23: label from --cbar-label
    cb.set_label(args.cbar_label, fontsize=fs)
    # jsasaki 2026-10-23: colour-bar ticks follow --font-size
    if fs:
        cb.ax.tick_params(labelsize=fs - 1)
    cb.ax.invert_yaxis()  # deeper downwards
    # jsasaki 2026-10-23: source line can be given for non-M7001 grids
    note = args.source_note or (f"Source: M7001 (JHA) converted to T.P., GMT surface DEM "
                                f"({args.dem.name}); land: OpenStreetMap via xcoast.")
    # jsasaki 2026-10-23: wrap long notes so they do not stretch the layout
    # jsasaki 2026-10-23: --no-note drops the source line
    if not args.no_note:
        ax.text(0.01, -0.11, note.replace("; ", "\n"), transform=ax.transAxes, fontsize=7,
                color="#52514e", va="top")
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    print(f"wrote {args.out}; depth range in region: "
          f"{float(np.nanmin(depth)):.1f} to {float(np.nanmax(depth)):.1f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
