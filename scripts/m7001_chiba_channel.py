#!/usr/bin/env python3
"""Correct the M7001 50 m T.P. DEM along the Chiba channel with the Endo (2020) 50 m grid.

M7001 (soundings gridded at 50 m) does not resolve the dredged Chiba channel: along its
axis M7001 gives 13-17 m in places where the Endo grid shows a flat channel floor at
about 19 m below T.P. Inside a corridor around the channel axis, M7001 is replaced by
the Endo depth (already shifted to T.P. on flat seabed, ``endo50m_to_tp.py``) wherever
Endo is deeper by more than --min-diff; the replacement is tapered to zero between
--half-width and --taper-width from the axis so no step is left at the corridor edge.
Cells deeper than --max-depth in Endo (the dredged borrow pits, being back-filled) are
not used. Everything outside the corridor is M7001 unchanged.

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

# channel axis (lon, lat), traced from the Endo grid (deepest cell per meridian)
AXIS = [(139.965, 35.5375), (139.98, 35.544), (140.00, 35.5555), (140.02, 35.566),
        (140.04, 35.5755), (140.06, 35.5865), (140.08, 35.5935)]


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    b = config.get_bathymetry_dir()
    ap.add_argument("--m7001", type=Path, default=b / "M7001" / "TP" / "M7001_dem_tokyobay_50m.nc")
    ap.add_argument("--endo", type=Path,
                    default=b / "tokyobay_endo" / "nc" / "endo_50m_lonlat_tp.nc")
    ap.add_argument("--half-width", type=float, default=500.0, help="full weight (m from axis)")
    ap.add_argument("--taper-width", type=float, default=700.0, help="zero weight (m from axis)")
    ap.add_argument("--min-diff", type=float, default=0.3, help="Endo deeper than M7001 by (m)")
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
    wgt = np.clip((args.taper_width - dist) / (args.taper_width - args.half_width), 0.0, 1.0)
    d_m, d_e = -sub.values, -endo.values
    use = (wgt > 0) & np.isfinite(d_m) & np.isfinite(d_e) & (d_e - d_m > args.min_diff) \
        & (d_e <= args.max_depth)
    delta = np.where(use, wgt * (d_e - d_m), 0.0)  # deepening (m, >= 0)
    new_sub = sub.values - delta

    out_elev = elev.copy()
    out_elev.loc[dict(lon=sub.lon, lat=sub.lat)] = new_sub
    out = ds.copy()
    out["elevation"] = out_elev.astype("float32")
    out["elevation"].attrs = dict(ds["elevation"].attrs)

    changed = delta > 0
    lat0 = np.radians(35.57)
    area_km2 = changed.sum() * (0.0005 * 111.32 * np.cos(lat0)) * (0.0005 * 111.32)
    axis_txt = "; ".join(f"{lo:.3f}E {la:.4f}N" for lo, la in AXIS)
    summary = (f"{int(changed.sum())} cells ({area_km2:.2f} km2) deepened; "
               f"deepening median {np.median(delta[changed]):.2f} m, max {delta.max():.2f} m; "
               f"corrected channel floor median {np.median(-new_sub[changed & (wgt == 1)]):.2f} m "
               f"below T.P.")
    out.attrs = dict(ds.attrs)
    out.attrs.update({
        "title": "M7001 50 m T.P. DEM of Tokyo Bay, Chiba channel corrected with the Endo (2020) 50 m grid",
        "chiba_channel_correction": (
            "M7001 does not resolve the dredged Chiba channel. Inside a corridor around the "
            f"channel axis ({axis_txt}), the depth is replaced by the Endo (2020) 50 m grid "
            "wherever Endo is deeper than M7001 by more than "
            f"{args.min_diff} m: depth = M7001 + w * (Endo - M7001), with w = 1 within "
            f"{args.half_width:.0f} m of the axis, tapering linearly to 0 at {args.taper_width:.0f} m. "
            f"Endo cells deeper than {args.max_depth} m (dredged borrow pits, being back-filled) "
            "are not used. Only deepening is applied; outside the corridor the grid is M7001 unchanged."),
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
