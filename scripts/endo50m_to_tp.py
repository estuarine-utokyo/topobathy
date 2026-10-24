#!/usr/bin/env python3
"""Convert the Endo (2020) 50 m Tokyo Bay grid to T.P., checked against M7001 on flat seabed.

Input: the lon/lat NetCDF from ``scripts/endo50m_to_lonlat.py`` (``elevation``, +up, datum
not stated). The source is believed to be an MLIT office product referenced to the
Arakawa datum A.P. (A.P. 0 m = T.P. -1.134 m), so depth below T.P. = depth below A.P.
+ 1.134 m, elevation (T.P.) = elevation (A.P.) - 1.134 m.

Check: dredged pits are being back-filled and harbours/channels are dredged, so depths
there changed between the surveys. Only flat seabed is compared with the M7001 T.P. DEM:
both depths in [--zmin, --zmax], local slope of both below --max-slope, and
|difference| below --max-diff (drops residual pits). The median offset on the flats is
printed overall, by depth band and by sub-area. M7001 is taken as correct: the
conversion shifts by minus the flat-seabed median (--shift flat, the default), and the
script stops if that shift is further than --tolerance from the A.P. value 1.134 m.

    python scripts/endo50m_to_tp.py --src .../endo_50m_lonlat.nc --out .../endo_50m_lonlat_tp.nc
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from topobathy import config

AP_BELOW_TP = 1.134  # A.P. 0 m = T.P. -1.134 m


def slope(depth: xr.DataArray) -> np.ndarray:
    """|grad depth| (m/m) on a lon/lat grid."""
    lat0 = np.radians(float(depth.lat.mean()))
    y = depth.lat.to_numpy() * 111_320.0  # coordinates in metres
    x = depth.lon.to_numpy() * 111_320.0 * np.cos(lat0)
    gy, gx = np.gradient(depth.to_numpy(), y, x)
    return np.hypot(gx, gy)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    # jsasaki 2026-10-23: owner: take M7001 as correct, shift by the flat-seabed median
    ap.add_argument("--shift", default="flat",
                    help="m added to depth, or 'flat' = minus the flat-seabed median "
                         "Endo - M7001 (default); A.P. -> T.P. would be 1.134")
    ap.add_argument("--zmin", type=float, default=3.0)
    ap.add_argument("--zmax", type=float, default=25.0)
    ap.add_argument("--max-slope", type=float, default=0.002, help="m/m (0.1 m per 50 m)")
    ap.add_argument("--max-diff", type=float, default=3.0)
    ap.add_argument("--tolerance", type=float, default=0.2)
    args = ap.parse_args()

    ds = xr.open_dataset(args.src)
    d_endo = -ds["elevation"].astype("float64")
    # jsasaki 2026-10-24: the M7001-only DEM was renamed when Futtsu took the default name
    m7 = config.get_bathymetry_dir() / "M7001" / "TP" / "M7001_dem_tokyobay_50m_m7001_only.nc"
    d_m7 = -xr.open_dataset(m7)["elevation"].astype("float64").interp(
        lon=d_endo.lon, lat=d_endo.lat, method="linear")

    diff = (d_endo - d_m7).to_numpy()  # + = Endo deeper
    e, m = d_endo.to_numpy(), d_m7.to_numpy()
    flat = (np.isfinite(diff) & (e >= args.zmin) & (e <= args.zmax) & (m >= args.zmin)
            & (m <= args.zmax) & (slope(d_endo) < args.max_slope)
            & (slope(d_m7) < args.max_slope) & (np.abs(diff) < args.max_diff))
    allw = np.isfinite(diff)

    def stats(mask) -> str:
        v = diff[mask]
        if v.size == 0:
            return "n=0"
        q25, q50, q75 = np.percentile(v, [25, 50, 75])
        return (f"n={v.size} median={q50:+.3f} m (IQR {q25:+.2f} to {q75:+.2f}) "
                f"mean={v.mean():+.3f} m")

    print(f"all water cells: {stats(allw)}")
    print(f"flat seabed ({args.zmin}-{args.zmax} m, slope<{args.max_slope}, "
          f"|diff|<{args.max_diff}): {stats(flat)}")
    for lo, hi in ((3, 8), (8, 13), (13, 18), (18, 25)):
        print(f"  flat, M7001 {lo}-{hi} m: {stats(flat & (m >= lo) & (m < hi))}")
    LON, LAT = np.meshgrid(d_endo.lon, d_endo.lat)
    for name, sel in (("NW (Tokyo/Kawasaki)", (LON < 139.9) & (LAT >= 35.55)),
                      ("NE (Funabashi/Chiba)", (LON >= 139.9) & (LAT >= 35.55)),
                      ("SW (Yokohama)", (LON < 139.9) & (LAT < 35.55)),
                      ("SE (Ichihara/Kisarazu)", (LON >= 139.9) & (LAT < 35.55))):
        print(f"  flat, {name}: {stats(flat & sel)}")

    med = float(np.median(diff[flat]))
    #---> jsasaki 2026-10-23: shift from the flats (M7001 taken as correct); the A.P. value
    # is kept as a plausibility check only
    if not np.isfinite(med):
        raise SystemExit(f"no flat-seabed cells; not writing {args.out}")
    shift = round(-med, 3) if args.shift == "flat" else float(args.shift)
    print(f"flat-seabed median Endo - M7001 = {med:+.3f} m; shift applied = {shift:+.3f} m; "
          f"A.P. would be {AP_BELOW_TP:+.3f} m")
    if abs(shift - AP_BELOW_TP) > args.tolerance:
        raise SystemExit(f"shift {shift:+.3f} m is more than {args.tolerance} m from the "
                         f"A.P. offset {AP_BELOW_TP} m; not writing {args.out}")
    args.shift = shift
    #<--- jsasaki 2026-10-23

    elev_tp = (ds["elevation"].astype("float64") - args.shift).astype("float32")
    elev_tp.attrs = {"units": "m", "positive": "up",
                     "long_name": "elevation above T.P. (negative = depth below T.P.)",
                     "vertical_datum": "T.P.",
                     # jsasaki 2026-10-23: record the flat-seabed shift, not the A.P. value
                     "conversion": f"elevation(T.P.) = elevation(source) - {args.shift} m, "
                                   "shift = flat-seabed median offset from M7001 (T.P.); "
                                   "source datum probably A.P. (A.P. 0 m = T.P. -1.134 m)"}
    out = xr.Dataset({"elevation": elev_tp}, coords={"lon": ds.lon, "lat": ds.lat},
                     attrs=dict(ds.attrs))
    out.attrs["history"] = (ds.attrs.get("history", "") +
                            # jsasaki 2026-10-23: shift fitted to M7001 on flat seabed
                            f"; to T.P. by -{args.shift} m fitted to M7001 on flat seabed, "
                            "scripts/endo50m_to_tp.py")
    out.attrs["datum_check"] = (f"flat seabed vs M7001 T.P. before conversion: median "
                                f"{med:+.3f} m (Endo - M7001 depth), n={int(flat.sum())}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(args.out, encoding={"elevation": {"zlib": True, "complevel": 4}})
    d_tp = d_endo + args.shift
    r = (d_tp - d_m7).to_numpy()
    print(f"wrote {args.out}; after conversion, flat seabed median Endo(T.P.) - M7001 = "
          f"{np.median(r[flat]):+.3f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
