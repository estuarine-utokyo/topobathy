#!/usr/bin/env python
"""Merge the MLIT Akanehama single-beam survey (off Narashino, ~410 x 520 m) into a T.P. DEM.

Input: the CSV of scripts/akanehama_points.py (depth below D.L. = T.P.-1.198 m, Chiba Lighthouse tide
station, from the reports' tide logs). Z(T.P.) = -depth - dl_offset. One survey (default: the latest,
2020-07-30 post-placement) is put on the base lattice (block median on a coarse lattice, linear
interpolation within one point spacing of a point on a fine lattice) and merged inside its
footprint with a linear edge ramp; only water cells of the base are changed.

  python scripts/akanehama_merge.py --base M7001_dem_tokyobay_50m.nc --points ak_pts.csv --out staging.nc
"""
from __future__ import annotations
import argparse
from datetime import date
from pathlib import Path
import numpy as np, pandas as pd, xarray as xr
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

SPACING = 10.0  # m, nominal point/line spacing of the survey


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--points", type=Path, required=True)
    ap.add_argument("--survey", default="2020-07-30_post")
    ap.add_argument("--dl-offset", type=float, default=1.198, help="T.P. - D.L. (m)")
    ap.add_argument("--min-coverage", type=float, default=0.5)
    ap.add_argument("--ramp", type=float, default=50.0, help="edge ramp width (m)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--diff-png", type=Path, default=None)
    a = ap.parse_args()

    ds = xr.open_dataset(a.base)
    base = ds["elevation"].astype("float64")
    lon, lat = base.lon.values, base.lat.values
    d = float(np.round(np.median(np.diff(lon)), 10))
    lat_c = np.radians(float(np.mean(lat)))
    dx, dy = d * 111_320.0 * np.cos(lat_c), d * 111_320.0
    cell_m2 = dx * dy
    p = pd.read_csv(a.points)
    p = p[p.survey == a.survey]
    if p.empty:
        raise SystemExit(f"no points for survey {a.survey}")
    z = -p.depth_dl_m.values - a.dl_offset
    fx, fy = (p.lon.values - lon[0]) / d, (p.lat.values - lat[0]) / d

    surv = np.full(base.shape, np.nan)
    if min(dx, dy) > 3.0 * SPACING:  # coarse lattice: block median
        ix, iy = np.rint(fx).astype(int), np.rint(fy).astype(int)
        g = pd.DataFrame({"iy": iy, "ix": ix, "z": z}).groupby(["iy", "ix"]).z
        med, cnt = g.median(), g.size()
        keep = cnt * SPACING**2 / cell_m2 >= a.min_coverage
        idx = med[keep].index
        surv[idx.get_level_values(0), idx.get_level_values(1)] = med[keep].values
        how = f"block median (cells with point coverage >= {a.min_coverage:g})"
    else:  # fine lattice: linear interpolation near a point
        pts = np.column_stack([fx, fy])
        lin, tree = LinearNDInterpolator(pts, z), cKDTree(pts)
        j0, j1 = int(np.floor(fy.min())) - 1, int(np.ceil(fy.max())) + 1
        i0, i1 = int(np.floor(fx.min())) - 1, int(np.ceil(fx.max())) + 1
        jj, ii = np.mgrid[j0:j1 + 1, i0:i1 + 1]
        zz = lin(ii.ravel().astype(float), jj.ravel().astype(float)).reshape(ii.shape)
        dist, _ = tree.query(np.column_stack([ii.ravel(), jj.ravel()]))
        zz[(dist * min(dx, dy) > SPACING * 1.0).reshape(ii.shape)] = np.nan
        surv[j0:j1 + 1, i0:i1 + 1] = zz
        how = f"linear interpolation within {SPACING:g} m of a point"
    fp = np.isfinite(surv)
    jy, jx = np.nonzero(fp)
    pad = int(np.ceil(a.ramp * 1.5 / min(dx, dy))) + 2
    sy = slice(max(jy.min() - pad, 0), min(jy.max() + pad + 1, lat.size))
    sx = slice(max(jx.min() - pad, 0), min(jx.max() + pad + 1, lon.size))
    bz, sv, fpw = base.values[sy, sx], surv[sy, sx], fp[sy, sx]
    both = fpw & np.isfinite(bz)
    dd = (sv - bz)[both]
    check = (f"survey - base elevation on {dd.size} overlapping water cells: median {np.median(dd):+.3f} m "
             f"(IQR {np.percentile(dd, 25):+.2f} to {np.percentile(dd, 75):+.2f}); survey {np.nanmin(sv):.2f} "
             f"to {np.nanmax(sv):.2f} m T.P.")
    print(check)

    inside = distance_transform_edt(fpw, sampling=(dy, dx))
    w = np.clip(inside / a.ramp, 0.0, 1.0)
    w[~fpw] = 0.0
    mw = np.where(both, w * sv + (1.0 - w) * bz, bz)
    changed = both & (w > 0)
    dm = (mw - bz)[changed]
    summary = (f"{int(changed.sum())} cells changed ({changed.sum() * cell_m2 / 1e6:.3f} km2), "
               f"{int((both & (w >= 1)).sum())} at full weight; merged - base median {np.median(dm):+.2f} m, "
               f"5-95 % {np.percentile(dm, 5):+.2f} to {np.percentile(dm, 95):+.2f} m")
    print(summary)

    merged = base.values.copy()
    merged[sy, sx] = mw
    out = ds.copy()
    out["elevation"] = xr.DataArray(merged.astype("float32"), dims=base.dims, coords=base.coords,
                                    attrs=dict(ds["elevation"].attrs))
    out["elevation"].attrs["source"] = (str(ds["elevation"].attrs.get("source", "")) +
        "; Akanehama: MLIT single-beam soil-placement survey (Akanehama_MLIT, D.L. -> T.P.)")
    today = date.today().isoformat()
    out.attrs.update({
        "akanehama_merge": (f"MLIT Akanehama single-beam survey {a.survey} (zone IX, depth below D.L. = "
            f"T.P.-{a.dl_offset:g} m) converted to T.P., placed by {how}; merged inside the survey "
            f"footprint with a linear ramp over {a.ramp:g} m; only water cells of the base are changed"),
        "akanehama_merge_datum_check": check,
        "akanehama_merge_summary": summary,
        "akanehama_merge_date": today,
        "akanehama_merge_script": "topobathy scripts/akanehama_merge.py",
        "history": (str(ds.attrs.get("history", "")) +
                    f"; {today}: Akanehama MLIT survey merged (scripts/akanehama_merge.py)").lstrip("; "),
    })
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(a.out, encoding={"elevation": {"zlib": True, "complevel": 4}})
    print(f"wrote {a.out}")
    if a.diff_png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        diff = np.where(changed, mw - bz, np.nan)
        fig, ax = plt.subplots(figsize=(6, 7))
        lim = float(np.nanpercentile(np.abs(diff), 98))
        pc = ax.pcolormesh(lon[sx], lat[sy], diff, cmap="RdBu", vmin=-lim, vmax=lim, shading="nearest")
        ax.contour(lon[sx], lat[sy], fpw.astype(float), levels=[0.5], colors="k", linewidths=0.6)
        ax.set_aspect(1 / np.cos(lat_c))
        ax.set_xlabel("Longitude (°E)"); ax.set_ylabel("Latitude (°N)")
        ax.ticklabel_format(useOffset=False, style="plain")
        fig.colorbar(pc, ax=ax, label="Merged - base elevation (m)")
        a.diff_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(a.diff_png, dpi=150, bbox_inches="tight")
        print(f"wrote {a.diff_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
