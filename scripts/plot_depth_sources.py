#!/usr/bin/env python3
"""Inner Tokyo Bay depth maps from bathymetry sources other than M7001.

Same frame and colours as docs/figures/tokyobay_inner_depth_tp.png (M7001):
cmocean ``deep``, 0-30 m, 5 m contours without labels, OSM land via xcoast.

Sources: Cabinet Office 2025 tsunami topography (CAO, 10/30/90 m, T.P.),
Japan Coast Guard 500 m mesh (mesh500), SRTM15+ (15 arc-second).

For each source the depth difference from the M7001 T.P. DEM (50 m) is printed over
cells where M7001 is 10-30 m deep, to show datum offsets and agreement.

    python scripts/plot_depth_sources.py --out-dir docs/figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from topobathy import config
from topobathy.io.grids import read_cao_2025, read_mesh500, read_srtm15plus
from topobathy.plot.depthmap import draw_depth_map

REGION = (139.60, 140.15, 35.36, 35.72)
FRAME = "Inner Tokyo Bay (north of Kisarazu)"


def m7001_depth() -> xr.DataArray:
    f = config.get_bathymetry_dir() / "M7001" / "TP" / "M7001_dem_tokyobay_50m.nc"
    w, e, s, n = REGION
    return -xr.open_dataset(f)["elevation"].sel(lon=slice(w, e), lat=slice(s, n))


def compare(name: str, src_at_ref: np.ndarray, ref: np.ndarray) -> str:
    ok = np.isfinite(src_at_ref) & np.isfinite(ref) & (ref >= 10) & (ref <= 30)
    d = src_at_ref[ok] - ref[ok]
    return (f"{name}: n={ok.sum()} median(source - M7001)={np.median(d):+.2f} m, "
            f"mean={d.mean():+.2f} m, RMS={np.sqrt((d ** 2).mean()):.2f} m "
            f"(M7001 depth 10-30 m T.P.; positive = source deeper)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, default=Path("docs/figures"))
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()
    ref = m7001_depth()
    report = []

    cao = read_cao_2025(REGION)
    out = draw_depth_map(
        REGION, args.out_dir / "tokyobay_inner_depth_cao2025.png", grid=cao, dpi=args.dpi,
        title=f"{FRAME}: Cabinet Office 2025, depth below T.P.",
        source_note="Source: Cabinet Office, Tokyo metropolitan earthquake model (2025) "
                    "tsunami topography, 10/30/90 m grids (processed); land: OpenStreetMap via xcoast.")
    print("wrote", out, "areas:", cao.attrs["areas"])
    report.append(compare("CAO 2025", cao.interp(lon=ref.lon, lat=ref.lat,
                                                 method="nearest").values, ref.values))

    m5 = read_mesh500(REGION)
    out = draw_depth_map(
        REGION, args.out_dir / "tokyobay_inner_depth_jcg500m.png",
        points=(m5.lon, m5.lat, m5.depth), dpi=args.dpi,
        title=f"{FRAME}: JCG 500 m mesh depth",
        source_note="Source: Japan Coast Guard 500 m mesh bathymetry (open data), "
                    "triangulated points; land: OpenStreetMap via xcoast.")
    print("wrote", out, f"points: {len(m5)}, flag counts: {m5.flag.value_counts().to_dict()}")
    at = ref.sel(lon=xr.DataArray(m5.lon.values), lat=xr.DataArray(m5.lat.values),
                 method="nearest").values
    inside = (m5.lon.between(REGION[0], REGION[1]) & m5.lat.between(REGION[2], REGION[3])).values
    report.append(compare("JCG 500 m", m5.depth.values[inside], at[inside]))

    sr = read_srtm15plus(REGION)
    out = draw_depth_map(
        REGION, args.out_dir / "tokyobay_inner_depth_srtm15plus.png", grid=sr, dpi=args.dpi,
        title=f"{FRAME}: SRTM15+ (15″) depth",
        source_note="Source: SRTM15+ V2.6 (Tozer et al. 2019), 15 arc-second global grid; "
                    "land: OpenStreetMap via xcoast.")
    print("wrote", out)
    report.append(compare("SRTM15+", sr.interp(lon=ref.lon, lat=ref.lat,
                                               method="nearest").values, ref.values))

    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
