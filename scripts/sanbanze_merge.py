#!/usr/bin/env python3
"""Merge the Chiba Prefecture Sanbanze surveys (10 m mesh, A.P.) into a Tokyo Bay T.P. DEM.

Source: ``$DATA_DIR/geodata/bathymetry/tokyo_bay/Sanbanze_Chiba_AP/csv/10m<era>JGD.csv``
(README and ``specification.pdf`` there). Columns ``X,Y,Z``: X = zone-IX *easting*, Y =
zone-IX *northing* (m), Z = depth in A.P. (m, negative below). ``Z >= 9000`` is a missing
value flag.

Steps

1. **datum** -- Z(T.P.) = Z(A.P.) - ``--ap-offset`` (nominal 1.1344 m: A.P. zero is below T.P.).
2. **epochs** -- ``--epochs H28,H24`` (priority order): a cell takes the first epoch that
   covers it, so the newest survey wins and older ones only fill the rest of the flat.
3. **to the DEM lattice** -- plane rectangular zone IX (JGD2000, EPSG:2451) -> lon/lat.
   A cell coarser than 3 survey meshes takes the median of the nodes in it (used only when
   the nodes cover at least ``--min-coverage`` of the cell); a finer cell takes a linear
   interpolation of the survey nodes, used only within ``--mesh-m`` of a node.
4. **datum check** -- on flat seabed (slope < 0.002, 1-20 m deep) survey minus base is
   reported (both are T.P. after step 1; no extra shift is applied).
5. **merge** -- inside the survey footprint the DEM takes the survey value, ramping
   linearly from the base at the footprint edge to the survey over ``--ramp`` m. Only cells
   that are water in the base change (its OSM land mask is kept).

Writes ``--out`` (CF NetCDF, ``elevation`` +up, T.P.) with the method in the global
attributes, and ``--diff-png`` (merged - base over the footprint).
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

from topobathy import config

CRS_SRC = "EPSG:2451"  # JGD2000 / plane rectangular zone IX (JGD2000 vs 2011: see README)


def slope(z: np.ndarray, dx: float, dy: float) -> np.ndarray:
    gy, gx = np.gradient(z, dy, dx)
    return np.hypot(gx, gy)


def read_epoch(path: Path, ap_offset: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    t = pd.read_csv(path, skipinitialspace=True, dtype=np.float64)
    t.columns = [c.strip() for c in t.columns]
    n0 = len(t)
    t = t[t.Z < 9000]
    return t.X.values, t.Y.values, t.Z.values - ap_offset, n0 - len(t)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    b = config.get_bathymetry_dir()
    ap.add_argument("--base", type=Path, required=True, help="T.P. DEM to merge into")
    ap.add_argument("--src", type=Path, default=b / "tokyo_bay" / "Sanbanze_Chiba_AP" / "csv")
    ap.add_argument("--epochs", default="H28,H24", help="survey years, priority order")
    ap.add_argument("--mesh-m", type=float, default=10.0, help="survey mesh (m)")
    ap.add_argument("--ap-offset", type=float, default=1.1344,
                    help="A.P. zero is this far below T.P. (m); nominal 1.1344")
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
    lat_c = np.radians(float(np.mean(lat)))
    dx = d * 111_320.0 * np.cos(lat_c)
    dy = d * 111_320.0
    cell_m2 = dx * dy
    block = min(dx, dy) > 3.0 * args.mesh_m
    to_ll = Transformer.from_crs(CRS_SRC, "EPSG:4326", always_xy=True)

    # 1-3. read epochs (priority order), convert, put on the lattice
    surv = np.full(base.shape, np.nan)
    epoch_of = np.zeros(base.shape, dtype=np.int8)  # 1-based index of the epoch used
    eps = [e.strip() for e in args.epochs.split(",")]
    per_epoch = {}
    notes = []
    for k, ep in enumerate(eps, start=1):
        f = args.src / f"10m{ep}JGD.csv"
        e, n, z, nflag = read_epoch(f, args.ap_offset)
        x, y = to_ll.transform(e, n)
        fx = (x - lon0) / d
        fy = (y - lat0) / d
        grid = np.full(base.shape, np.nan)
        if block:
            ix, iy = np.rint(fx).astype(np.int64), np.rint(fy).astype(np.int64)
            ok = (ix >= 0) & (ix < lon.size) & (iy >= 0) & (iy < lat.size)
            df = pd.DataFrame({"iy": iy[ok], "ix": ix[ok], "z": z[ok]})
            g = df.groupby(["iy", "ix"]).z
            med, cnt = g.median(), g.size()
            keep = cnt * args.mesh_m**2 / cell_m2 >= args.min_coverage
            idx = med[keep].index
            grid[idx.get_level_values(0), idx.get_level_values(1)] = med[keep].values
        else:
            # linear interpolation of the survey nodes, near a node only
            pts = np.column_stack([fx, fy])
            lin = LinearNDInterpolator(pts, z)
            tree = cKDTree(pts)
            j0, j1 = int(np.floor(fy.min())) - 1, int(np.ceil(fy.max())) + 1
            i0, i1 = int(np.floor(fx.min())) - 1, int(np.ceil(fx.max())) + 1
            j0, i0 = max(j0, 0), max(i0, 0)
            j1, i1 = min(j1, lat.size - 1), min(i1, lon.size - 1)
            jj, ii = np.mgrid[j0:j1 + 1, i0:i1 + 1]
            zz = lin(ii.ravel().astype(float), jj.ravel().astype(float)).reshape(ii.shape)
            dist, _ = tree.query(np.column_stack([ii.ravel(), jj.ravel()]))
            far = (dist * min(dx, dy)).reshape(ii.shape) > args.mesh_m
            zz[far] = np.nan
            grid[j0:j1 + 1, i0:i1 + 1] = zz
        per_epoch[ep] = grid
        new = np.isfinite(grid) & ~np.isfinite(surv)
        surv[new] = grid[new]
        epoch_of[new] = k
        notes.append(f"{ep}: {len(z)} nodes ({nflag} flagged Z>=9000 dropped), "
                     f"{int(np.isfinite(grid).sum())} cells, {int(new.sum())} used")
        print(notes[-1])
    fp = np.isfinite(surv)
    jy, jx = np.nonzero(fp)
    print(f"survey elevation {np.nanmin(surv):.2f} to {np.nanmax(surv):.2f} m T.P.; footprint "
          f"lon {lon[jx.min()]:.4f}-{lon[jx.max()]:.4f}, lat {lat[jy.min()]:.4f}-{lat[jy.max()]:.4f}")

    # epoch agreement where both cover a cell (seam of the newest epoch inside the older)
    seam = ""
    if len(eps) > 1:
        a, c = per_epoch[eps[0]], per_epoch[eps[1]]
        ov = np.isfinite(a) & np.isfinite(c)
        if ov.any():
            dd = (a - c)[ov]
            seam = (f"{eps[0]} - {eps[1]} where both cover: median {np.median(dd):+.3f} m "
                    f"(5-95 % {np.percentile(dd, 5):+.2f} to {np.percentile(dd, 95):+.2f}), "
                    f"n={dd.size}")
            print(seam)

    # work inside a window around the footprint (the 10 m grid is large)
    padc = int(np.ceil(args.ramp * 1.5 / min(dx, dy))) + 2
    sy = slice(max(jy.min() - padc, 0), min(jy.max() + padc + 1, lat.size))
    sx = slice(max(jx.min() - padc, 0), min(jx.max() + padc + 1, lon.size))
    bz = base.values[sy, sx]
    sv = surv[sy, sx]
    fpw = fp[sy, sx]

    # 4. datum check on flat seabed
    both = fpw & np.isfinite(bz)
    flat = both & (slope(np.where(np.isfinite(bz), bz, 0.0), dx, dy) < 0.002) \
        & (slope(np.where(fpw, sv, 0.0), dx, dy) < 0.002) & (bz < -1) & (bz > -20) \
        & (sv < -1) & (sv > -20)
    dif = (sv - bz)[flat]
    dall = (sv - bz)[both]
    check = (f"survey - base elevation on flat seabed (1-20 m, slope < 0.002): median "
             f"{np.median(dif):+.3f} m (IQR {np.percentile(dif, 25):+.2f} to "
             f"{np.percentile(dif, 75):+.2f}), n={dif.size}; all overlapping water cells: "
             f"median {np.median(dall):+.3f} m, n={dall.size}")
    print(check)

    # 5. merge with an edge ramp, water cells of the base only
    inside = distance_transform_edt(fpw, sampling=(dy, dx))
    w = np.clip(inside / args.ramp, 0.0, 1.0)
    w[~fpw] = 0.0
    mw = np.where(both, w * sv + (1.0 - w) * bz, bz)
    changed = both & (w > 0)
    dm = (mw - bz)[changed]
    summary = (f"{int(changed.sum())} cells changed ({changed.sum() * cell_m2 / 1e6:.2f} km2), "
               f"{int((both & (w >= 1)).sum())} at full weight; merged - base median "
               f"{np.median(dm):+.2f} m, 5-95 % {np.percentile(dm, 5):+.2f} to "
               f"{np.percentile(dm, 95):+.2f} m")
    print(summary)

    merged = base.values.copy()
    merged[sy, sx] = mw
    out = base_ds.copy()
    out["elevation"] = xr.DataArray(merged.astype("float32"), dims=base.dims,
                                    coords=base.coords, attrs=dict(base_ds["elevation"].attrs))
    out["elevation"].attrs["source"] = (
        str(base_ds["elevation"].attrs.get("source", "")) +
        "; Sanbanze: Chiba Prefecture surveys (Sanbanze_Chiba_AP, 10 m, A.P. -> T.P.)")
    today = date.today().isoformat()
    out.attrs.update({
        "title": (f"{base_ds.attrs.get('title', args.base.name)}; Sanbanze merged (Chiba "
                  f"Prefecture surveys {'+'.join(eps)}), {d:g} deg grid"),
        "sanbanze_merge": (
            f"Chiba Prefecture Sanbanze 10 m surveys {', '.join(eps)} (priority order; "
            f"{args.src}; {CRS_SRC}, depth in A.P.) converted to T.P. with Z(T.P.) = Z(A.P.) - "
            f"{args.ap_offset:g} m (nominal), placed on this lattice by "
            f"{'block median (cells with node coverage >= %g)' % args.min_coverage if block else 'linear interpolation within %g m of a node' % args.mesh_m}; "
            f"merged into {args.base.name} inside the survey footprint with a linear ramp over "
            f"{args.ramp:g} m inside the footprint edge; only water cells of the base are "
            "changed (its OSM land mask is kept)"),
        "sanbanze_merge_epochs": "; ".join(notes),
        "sanbanze_merge_epoch_seam": seam,
        "sanbanze_merge_datum_check": check,
        "sanbanze_merge_summary": summary,
        "sanbanze_merge_date": today,
        "sanbanze_merge_script": "topobathy scripts/sanbanze_merge.py",
        "history": (str(base_ds.attrs.get("history", "")) +
                    f"; {today}: Sanbanze Chiba surveys merged (scripts/sanbanze_merge.py)"
                    ).lstrip("; "),
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(args.out, encoding={"elevation": {"zlib": True, "complevel": 4}})
    print(f"wrote {args.out}")

    if args.diff_png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        diff = np.where(changed, mw - bz, np.nan)
        fig, ax = plt.subplots(figsize=(7, 8))
        lim = float(np.nanpercentile(np.abs(diff), 98))
        pc = ax.pcolormesh(lon[sx], lat[sy], diff, cmap="RdBu", vmin=-lim, vmax=lim,
                           shading="nearest")
        ax.contour(lon[sx], lat[sy], fpw.astype(float), levels=[0.5], colors="k",
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
