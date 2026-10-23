#!/usr/bin/env python3
"""Correct the M7001 50 m T.P. DEM along the Chiba channel with the Endo (2020) 50 m grid.

M7001 (soundings gridded at 50 m) does not resolve the dredged Chiba channel: along its
axis M7001 gives 13-17 m in places where the Endo grid shows a flat channel floor at
about 19 m below T.P., and the channel soundings it does hold are smeared into bumps on
the surrounding flat seabed. The correction therefore has two steps:

1. flat seabed: inside a corridor of --fill-width around the channel axis, M7001 is
   discarded and refilled by a harmonic (Laplace) interpolation from the M7001 values
   just outside the corridor, giving smooth contours across the corridor;
2. channel: a straight dredged channel is cut along the axis with the cross-section
   measured from the Endo grid (shifted to T.P. on flat seabed, ``endo50m_to_tp.py``):
   flat floor at the Endo median depth within 100 m of the axis, out to
   --floor-half-width, then --side-slope up to the smooth surface;
   depth = max(smooth, channel profile). The corridor ends are cut square to the axis.

Endo cells deeper than --max-depth (dredged borrow pits, being back-filled) are not
used. Everything outside the corridor is M7001 unchanged.

Both grids are on the same 0.0005 deg lattice; the Endo values are taken by nearest cell.

    python scripts/m7001_chiba_channel.py --out .../M7001_dem_tokyobay_50m_chiba_channel.nc
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import xarray as xr

from topobathy import config

#---> jsasaki 2026-10-23: axis = centre of the Endo channel floor (> 18.7 m): straight leg
# lat = 0.51672 lon - 36.78583 (139.975-140.06 E, rms 32 m), then the bend to the port mouth
# extended south-west to 139.94 E, where the natural depth reaches the channel floor
AXIS = [(139.940, 35.5246), (140.062, 35.5876), (140.070, 35.5905), (140.085, 35.5920)]
#<--- jsasaki 2026-10-23


def dist_to_polyline(lon, lat, axis) -> np.ndarray:
    """Distance (m) from each point to the polyline, local equirectangular metres."""
    lat0 = np.radians(np.mean([p[1] for p in axis]))
    kx, ky = 111_320.0 * np.cos(lat0), 111_320.0
    px, py = lon * kx, lat * ky
    d = np.full(px.shape, np.inf)
    for (x1, y1), (x2, y2) in zip(axis[:-1], axis[1:]):
        ax, ay, bx, by = x1 * kx, y1 * ky, x2 * kx, y2 * ky
        vx, vy = bx - ax, by - ay
        t = np.clip(((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy), 0.0, 1.0)
        d = np.minimum(d, np.hypot(px - (ax + t * vx), py - (ay + t * vy)))
    return d


#---> jsasaki 2026-10-23: corridor ends cut square to the axis (no round caps into the port)
def beyond_ends(lon, lat, axis) -> np.ndarray:
    """True where a point lies before the first or after the last axis vertex, measured
    along the end segments."""
    lat0 = np.radians(np.mean([p[1] for p in axis]))
    kx, ky = 111_320.0 * np.cos(lat0), 111_320.0
    px, py = lon * kx, lat * ky
    (x0, y0), (x1, y1) = axis[0], axis[1]
    before = ((px - x0 * kx) * (x1 - x0) * kx + (py - y0 * ky) * (y1 - y0) * ky) < 0
    (x0, y0), (x1, y1) = axis[-2], axis[-1]
    after = ((px - x1 * kx) * (x1 - x0) * kx + (py - y1 * ky) * (y1 - y0) * ky) > 0
    return before | after
#<--- jsasaki 2026-10-23


#---> jsasaki 2026-10-23: owner: flats beside the channel must be smooth (harmonic refill)
def harmonic_fill(z: np.ndarray, unknown: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Solve Laplace(z) = 0 on the unknown cells; finite neighbours are Dirichlet values,
    NaN neighbours (land) are no-flux. dx, dy = cell size (m)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve

    ny, nx = z.shape
    idx = -np.ones(z.shape, dtype=np.int64)
    iy, ix = np.nonzero(unknown)
    idx[iy, ix] = np.arange(iy.size)
    rows, cols, vals = [], [], []
    diag = np.zeros(iy.size)
    rhs = np.zeros(iy.size)
    for oy, ox, wgt in ((1, 0, 1 / dy ** 2), (-1, 0, 1 / dy ** 2),
                        (0, 1, 1 / dx ** 2), (0, -1, 1 / dx ** 2)):
        jy, jx = iy + oy, ix + ox
        ok = (jy >= 0) & (jy < ny) & (jx >= 0) & (jx < nx)
        k = np.nonzero(ok)[0]
        nb_idx = idx[jy[k], jx[k]]
        nb_val = z[jy[k], jx[k]]
        unk = nb_idx >= 0
        known = ~unk & np.isfinite(nb_val)
        diag[k[unk | known]] += wgt
        rows.append(k[unk]); cols.append(nb_idx[unk]); vals.append(np.full(unk.sum(), -wgt))
        rhs[k[known]] += wgt * nb_val[known]
    rows.append(np.arange(iy.size)); cols.append(np.arange(iy.size)); vals.append(diag)
    a = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                   shape=(iy.size, iy.size)).tocsr()
    out = z.copy()
    out[iy, ix] = spsolve(a, rhs)
    return out
#<--- jsasaki 2026-10-23


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    b = config.get_bathymetry_dir()
    ap.add_argument("--m7001", type=Path, default=b / "M7001" / "TP" / "M7001_dem_tokyobay_50m.nc")
    ap.add_argument("--endo", type=Path,
                    default=b / "tokyobay_endo" / "nc" / "endo_50m_lonlat_tp.nc")
    #---> jsasaki 2026-10-23: harmonic refill of the flats + channel cut (replaces the taper)
    ap.add_argument("--fill-width", type=float, default=900.0,
                    help="corridor half-width refilled smoothly (m from axis)")
    # jsasaki 2026-10-23: straight channel cross-section measured from the Endo grid
    ap.add_argument("--floor-half-width", type=float, default=175.0,
                    help="half-width of the flat channel floor (m)")
    ap.add_argument("--side-slope", type=float, default=0.04,
                    help="side slope (m/m) from the floor edge up to the flat seabed")
    #<--- jsasaki 2026-10-23
    ap.add_argument("--max-depth", type=float, default=20.0, help="ignore Endo deeper than (m)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    ds = xr.open_dataset(args.m7001)
    elev = ds["elevation"].astype("float64")
    w, e = min(p[0] for p in AXIS) - 0.02, max(p[0] for p in AXIS) + 0.02
    s, n = min(p[1] for p in AXIS) - 0.02, max(p[1] for p in AXIS) + 0.02
    sub = elev.sel(lon=slice(w, e), lat=slice(s, n))
    endo = xr.open_dataset(args.endo)["elevation"].astype("float64").reindex(
        lon=sub.lon, lat=sub.lat, method="nearest", tolerance=1e-6)

    LON, LAT = np.meshgrid(sub.lon.values, sub.lat.values)
    dist = dist_to_polyline(LON, LAT, AXIS)
    #---> jsasaki 2026-10-23: step 1 smooth flats (harmonic refill), step 2 cut the channel

    d_m, d_e = -sub.values, -endo.values
    lat0 = np.radians(float(sub.lat.mean()))
    dx = 0.0005 * 111_320.0 * np.cos(lat0)
    dy = 0.0005 * 111_320.0
    corridor = (dist <= args.fill_width) & np.isfinite(d_m) & ~beyond_ends(LON, LAT, AXIS)
    smooth = harmonic_fill(np.where(corridor, np.nan, d_m), corridor, dx, dy)
    ok_e = np.isfinite(d_e) & (d_e <= args.max_depth)
    # channel floor depth: median Endo within 100 m of the axis
    floor = float(np.median(d_e[corridor & ok_e & (dist <= 100.0)]))
    profile = floor - args.side_slope * np.clip(dist - args.floor_half_width, 0.0, None)
    channel = corridor & (profile > smooth)
    new_depth = np.where(corridor, smooth, d_m)
    new_depth = np.where(channel, profile, new_depth)
    new_sub = -new_depth
    delta = new_depth - d_m  # + = deeper than M7001
    #<--- jsasaki 2026-10-23

    out_elev = elev.copy()
    out_elev.loc[dict(lon=sub.lon, lat=sub.lat)] = new_sub
    out = ds.copy()
    out["elevation"] = out_elev.astype("float32")
    out["elevation"].attrs = dict(ds["elevation"].attrs)

    #---> jsasaki 2026-10-23: summary for the two-step correction
    cell_km2 = dx * dy / 1e6
    axis_txt = "; ".join(f"{lo:.3f}E {la:.4f}N" for lo, la in AXIS)
    flat = corridor & ~channel
    summary = (f"corridor {int(corridor.sum())} cells ({corridor.sum() * cell_km2:.2f} km2), "
               f"of which channel {int(channel.sum())} cells ({channel.sum() * cell_km2:.2f} km2); "
               f"flat-seabed change (smooth - M7001) median {np.median(delta[flat]):+.2f} m, "
               f"5-95 % {np.percentile(delta[flat], 5):+.2f} to {np.percentile(delta[flat], 95):+.2f} m; "
               f"channel deepening median {np.median(delta[channel]):+.2f} m, "
               f"max {delta[channel].max():+.2f} m; channel floor median "
               f"{floor:.2f} m below T.P. (Endo median within 100 m of the axis)")
    #<--- jsasaki 2026-10-23
    out.attrs = dict(ds.attrs)
    out.attrs.update({
        "title": "M7001 50 m T.P. DEM of Tokyo Bay, Chiba channel corrected with the Endo (2020) 50 m grid",
        "chiba_channel_correction": (
            # jsasaki 2026-10-23: describe the two-step correction
            "M7001 does not resolve the dredged Chiba channel and smears its soundings into "
            "bumps on the flat seabed beside it. (1) Flat seabed: within "
            f"{args.fill_width:.0f} m of the channel axis ({axis_txt}) M7001 is discarded and "
            "refilled by harmonic (Laplace) interpolation from the M7001 values just outside "
            "this corridor (land cells no-flux; the corridor ends are cut square to the axis). "
            "(2) Channel: a straight dredged channel is cut along the axis with the cross-section "
            "measured from the Endo (2020) 50 m grid: flat floor at "
            f"{floor:.2f} m below T.P. (Endo median within 100 m of the axis) to "
            f"{args.floor_half_width:.0f} m from the axis, side slope {args.side_slope} m/m up to "
            "the refilled surface; depth = max(refilled, channel profile). Endo cells deeper than "
            f"{args.max_depth} m (dredged borrow pits, being back-filled) are not used. Outside "
            "the corridor the grid is M7001 unchanged."),
        "chiba_channel_correction_source": (
            f"{args.endo}: Endo (2020) 50 m Tokyo Bay grid shifted to T.P. by its flat-seabed "
            "median offset from M7001 (scripts/endo50m_to_tp.py)"),
        "chiba_channel_correction_summary": summary,
        "chiba_channel_correction_date": date.today().isoformat(),
        "chiba_channel_correction_script": "topobathy scripts/m7001_chiba_channel.py",
        "history": (ds.attrs.get("history", "") +
                    f"; {date.today().isoformat()}: Chiba channel corrected with Endo (2020) 50 m "
                    "(scripts/m7001_chiba_channel.py)").lstrip("; "),
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(args.out, encoding={"elevation": {"zlib": True, "complevel": 4}})
    print(f"wrote {args.out}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
