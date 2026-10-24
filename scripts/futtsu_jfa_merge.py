#!/usr/bin/env python3
"""Merge the Fisheries Agency 2022 Futtsu survey (0.5 m, T.P.) into the 50 m Tokyo Bay DEM.

Source: ``$DATA_DIR/geodata/bathymetry/Futtsu_JFA_2023/05MCSV_TP/*.txt`` -- 43 tiles of a
0.5 m grid (800 x 600 nodes per 400 m x 300 m tile), columns ``id, easting, northing,
elevation, flag`` in JGD2011 plane rectangular zone IX (EPSG:6677), elevation in m above
T.P. (negative below). ``MESH_TP/`` holds byte-identical copies; ``ORIGINAL_TP/`` (the raw
point cloud) is not used.

Steps

1. **block median to the DEM lattice** -- every 0.5 m node is assigned to the 0.0005 deg
   cell of the base DEM that contains it (EPSG:6677 -> lon/lat), and each cell takes the
   median of its nodes. A cell is used only when its nodes cover at least
   ``--min-coverage`` of it (nodes x 0.25 m^2 / cell area), so the partly covered cells
   at the survey edge do not carry a value biased to one corner.
2. **datum check** -- on flat seabed (both slopes < 0.002, depth 1-20 m) the survey is
   compared with the base DEM; both are T.P., so no shift is applied, the median
   difference is reported and recorded.
3. **merge** -- inside the survey footprint the DEM takes the survey value, ramping
   linearly from the base DEM at the footprint edge to the survey over ``--ramp`` m
   (distance inside the footprint), so no step is left. Only cells that are water in the
   base DEM are changed: its hydro-flattened land mask (OSM coastline) is kept.

Writes ``--out`` (CF NetCDF, ``elevation`` +up, T.P.) with the method in the global
attributes, and ``--diff-png`` (merged - base over the footprint).

    python scripts/futtsu_jfa_merge.py --base .../M7001_dem_tokyobay_50m_chiba_channel.nc \
        --out .../M7001_dem_tokyobay_50m_futtsu.nc
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer
from scipy.ndimage import distance_transform_edt

from topobathy import config


def slope(z: np.ndarray, dx: float, dy: float) -> np.ndarray:
    gy, gx = np.gradient(z, dy, dx)
    return np.hypot(gx, gy)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    b = config.get_bathymetry_dir()
    ap.add_argument("--base", type=Path, required=True, help="50 m T.P. DEM to merge into")
    ap.add_argument("--src", type=Path, default=b / "Futtsu_JFA_2023" / "05MCSV_TP")
    ap.add_argument("--min-coverage", type=float, default=0.5)
    ap.add_argument("--ramp", type=float, default=250.0, help="edge ramp width (m)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--diff-png", type=Path, default=None)
    args = ap.parse_args()

    base_ds = xr.open_dataset(args.base)
    base = base_ds["elevation"].astype("float64")
    lon = base.lon.values
    lat = base.lat.values
    d = float(np.round(np.median(np.diff(lon)), 10))
    lon0, lat0 = lon[0], lat[0]

    # 1. read the tiles and block-median to the lattice
    files = sorted(args.src.glob("*.txt"))
    if len(files) == 0:
        raise SystemExit(f"no tiles in {args.src}")
    to_ll = Transformer.from_crs("EPSG:6677", "EPSG:4326", always_xy=True)
    parts = []
    nodes = 0
    for f in files:
        t = pd.read_csv(f, header=None, names=["id", "e", "n", "z", "flag"],
                        usecols=["e", "n", "z"], dtype=np.float64)
        t = t[t.z > -9000]
        nodes += len(t)
        x, y = to_ll.transform(t.e.values, t.n.values)
        ix = np.rint((x - lon0) / d).astype(np.int64)
        iy = np.rint((y - lat0) / d).astype(np.int64)
        parts.append(pd.DataFrame({"iy": iy, "ix": ix, "z": t.z.values}))
    pts = pd.concat(parts, ignore_index=True)
    ok = (pts.ix >= 0) & (pts.ix < lon.size) & (pts.iy >= 0) & (pts.iy < lat.size)
    pts = pts[ok]
    g = pts.groupby(["iy", "ix"]).z
    med = g.median()
    cnt = g.size()
    lat_c = np.radians(float(np.mean(lat)))
    cell_m2 = (d * 111_320.0 * np.cos(lat_c)) * (d * 111_320.0)
    cover = cnt * 0.25 / cell_m2
    keep = cover >= args.min_coverage
    surv = np.full(base.shape, np.nan)
    idx = med[keep].index
    surv[idx.get_level_values(0), idx.get_level_values(1)] = med[keep].values
    print(f"{len(files)} tiles, {nodes} nodes; {int(keep.sum())} cells with coverage >= "
          f"{args.min_coverage} (of {len(med)} touched); survey elevation "
          f"{np.nanmin(surv):.2f} to {np.nanmax(surv):.2f} m T.P.")
    fp = np.isfinite(surv)
    jy, jx = np.nonzero(fp)
    print(f"footprint lon {lon[jx.min()]:.4f}-{lon[jx.max()]:.4f}, "
          f"lat {lat[jy.min()]:.4f}-{lat[jy.max()]:.4f}")

    # 2. datum check on flat seabed
    bz = base.values
    dx = d * 111_320.0 * np.cos(lat_c)
    dy = d * 111_320.0
    both = fp & np.isfinite(bz)
    flat = both & (slope(np.where(np.isfinite(bz), bz, 0.0), dx, dy) < 0.002) \
        & (slope(np.where(fp, surv, 0.0), dx, dy) < 0.002) & (bz < -1) & (bz > -20) \
        & (surv < -1) & (surv > -20)
    dif = (surv - bz)[flat]
    dall = (surv - bz)[both]
    check = (f"survey - base elevation on flat seabed (1-20 m, slope < 0.002): median "
             f"{np.median(dif):+.3f} m (IQR {np.percentile(dif, 25):+.2f} to "
             f"{np.percentile(dif, 75):+.2f}), n={dif.size}; all overlapping water cells: "
             f"median {np.median(dall):+.3f} m, n={dall.size}")
    print(check)

    # 3. merge with an edge ramp, water cells of the base only
    inside = distance_transform_edt(fp, sampling=(dy, dx))
    w = np.clip(inside / args.ramp, 0.0, 1.0)
    w[~fp] = 0.0
    merged = np.where(both, w * surv + (1.0 - w) * bz, bz)
    changed = both & (w > 0)
    dm = (merged - bz)[changed]
    summary = (f"{int(changed.sum())} cells changed ({changed.sum() * dx * dy / 1e6:.2f} km2), "
               f"{int((both & (w >= 1)).sum())} at full weight; merged - base median "
               f"{np.median(dm):+.2f} m, 5-95 % {np.percentile(dm, 5):+.2f} to "
               f"{np.percentile(dm, 95):+.2f} m")
    print(summary)

    out = base_ds.copy()
    out["elevation"] = xr.DataArray(merged.astype("float32"), dims=base.dims,
                                    coords=base.coords, attrs=dict(base_ds["elevation"].attrs))
    out["elevation"].attrs["source"] = (
        str(base_ds["elevation"].attrs.get("source", "")) +
        "; Futtsu: Fisheries Agency 2022 survey (Futtsu_JFA_2023, 0.5 m, T.P.)")
    today = date.today().isoformat()
    out.attrs.update({
        "title": "Tokyo Bay 50 m T.P. DEM: M7001, Chiba channel corrected (Endo 2020), "
                 "Futtsu merged (Fisheries Agency 2022 survey)",
        "futtsu_merge": (
            f"Fisheries Agency 2022 Futtsu survey ({args.src}, {len(files)} tiles of a 0.5 m "
            "grid, EPSG:6677, elevation above T.P.) block-medianed to this 0.0005 deg lattice "
            f"(cells with node coverage >= {args.min_coverage}); merged into {args.base.name} "
            f"inside the survey footprint with a linear ramp over {args.ramp:g} m inside the "
            "footprint edge (base at the edge, survey at full weight); only water cells of the "
            "base are changed (its OSM land mask is kept); no datum shift (both T.P.)"),
        "futtsu_merge_datum_check": check,
        "futtsu_merge_summary": summary,
        "futtsu_merge_date": today,
        "futtsu_merge_script": "topobathy scripts/futtsu_jfa_merge.py",
        "history": (str(base_ds.attrs.get("history", "")) +
                    f"; {today}: Futtsu JFA 2022 survey merged (scripts/futtsu_jfa_merge.py)"
                    ).lstrip("; "),
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(args.out, encoding={"elevation": {"zlib": True, "complevel": 4}})
    print(f"wrote {args.out}")

    if args.diff_png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pad = 0.01
        sx = slice(max(jx.min() - int(pad / d), 0), jx.max() + int(pad / d))
        sy = slice(max(jy.min() - int(pad / d), 0), jy.max() + int(pad / d))
        diff = np.where(changed, merged - bz, np.nan)[sy, sx]
        fig, ax = plt.subplots(figsize=(7, 6))
        lim = float(np.nanpercentile(np.abs(diff), 98))
        pc = ax.pcolormesh(lon[sx], lat[sy], diff, cmap="RdBu", vmin=-lim, vmax=lim,
                           shading="nearest")
        ax.contour(lon[sx], lat[sy], fp[sy, sx].astype(float), levels=[0.5], colors="k",
                   linewidths=0.6)
        ax.set_aspect(1 / np.cos(lat_c))
        ax.set_xlabel("Longitude (°E)")
        ax.set_ylabel("Latitude (°N)")
        ax.ticklabel_format(useOffset=False, style="plain")
        fig.colorbar(pc, ax=ax, label="Merged - base elevation (m)")
        args.diff_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.diff_png, dpi=150, bbox_inches="tight")
        print(f"wrote {args.diff_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
