"""CLI: convert the JHA / Japan Coast Guard M7001 chart-datum bathymetry to T.P.

Reads the M7001 (Southern Kanto) J-BIRD ASCII file (referenced to 基本水準面 /
chart datum ≈ lowest water), applies a spatially-varying chart-datum -> T.P.
offset ``Z0(x, y) = T.P. − 基本水準面`` from the JMA/JCG tide-station separation
model (see ``docs/vertical_datum.md``), and writes a T.P.-referenced point dataset
to ``$DATA_DIR/bathymetry/M7001/TP/``.

Output columns: ``mark, lon, lat, z_tp, depth_cd, z0, unit, geodetic`` where
``z_tp`` is the **T.P. elevation (m, positive up; seabed negative)**; ``depth_cd``
is the original chart-datum vertical value and ``z0`` the applied offset, both
retained for traceability (a T.P. depth, positive down, is ``-z_tp``).

This is heavy for the full ~3.95 M-point sheet — run it as a batch job
(``scripts/genkai_m7001_to_tp.sh``), not on the HPC login node.

Example
-------
    topobathy-m7001-to-tp --formats csv parquet
    topobathy-m7001-to-tp --marks N --formats parquet --max-records 200000  # preview
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from topobathy import config
from topobathy.datum import GeoidModel, SeparationModel, add_tp_elevation
from topobathy.io import BBox, read_jbird, write_points

_SOURCE_LABEL = "JHA/JCG M7001 (Southern Kanto, Ver.2.4), J-BIRD chart-datum ASCII"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="topobathy-m7001-to-tp",
        description="Convert M7001 chart-datum (最低水面基準) bathymetry to T.P.",
    )
    p.add_argument(
        "--source",
        type=Path,
        default=None,
        help="M7001 J-BIRD file (default: $DATA_DIR/bathymetry/M7001/ascii/...)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output directory (default: $DATA_DIR/bathymetry/M7001/TP)",
    )
    p.add_argument(
        "--out-name",
        default="M7001_TP",
        help="output basename without extension (default: M7001_TP)",
    )
    p.add_argument(
        "--marks",
        nargs="+",
        default=["N", "M", "L"],
        metavar="MARK",
        help="J-BIRD marks to convert (default: N M L)",
    )
    p.add_argument(
        "--formats",
        nargs="+",
        default=["csv", "parquet"],
        choices=["csv", "parquet", "netcdf"],
        help="output formats (default: csv parquet)",
    )
    p.add_argument(
        "--z0-table",
        type=Path,
        default=None,
        help="tide-station datum CSV lon,lat,tp_minus_cd_m "
        "(default: bundled kanto_south_tp_minus_cd.csv)",
    )
    p.add_argument(
        "--z0-power", type=float, default=2.0, help="IDW exponent for Z0 (default: 2)"
    )
    p.add_argument(
        "--method",
        default="idw",
        choices=["idw", "linear", "cubic", "tps"],
        help="separation interpolation (default: idw)",
    )
    p.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        default=None,
        metavar=("LON_MIN", "LON_MAX", "LAT_MIN", "LAT_MAX"),
        help="optional geographic bounding box filter",
    )
    p.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="scan only the first N records (preview / smoke test)",
    )
    p.add_argument(
        "--geoid",
        type=Path,
        nargs="?",
        const="__default__",
        default=None,
        help="add a z_ell (WGS84 ellipsoidal height) column via a GSI geoid .asc "
        "(no path -> the bundled $DATA_DIR/geoid default); see scripts/get_gsigeo.py",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    source = args.source or config.m7001_source_file()
    out_dir = args.out_dir or config.m7001_tp_dir()
    z0_table = args.z0_table or config.default_z0_table()
    bbox = BBox(*args.bbox) if args.bbox else None

    print(f"source     : {source}", flush=True)
    print(f"marks      : {' '.join(args.marks)}", flush=True)
    print(f"z0 table   : {z0_table}", flush=True)
    if bbox:
        print(f"bbox       : {bbox}", flush=True)

    df = read_jbird(source, marks=args.marks, bbox=bbox, max_records=args.max_records)
    if df.empty:
        print("ERROR: no points read (check marks / bbox / source).", file=sys.stderr)
        return 1
    counts = df["mark"].value_counts().to_dict()
    print(f"read       : {len(df):,} points {counts}", flush=True)

    model = SeparationModel.from_csv(z0_table, power=args.z0_power, method=args.method)
    df = add_tp_elevation(df, model)
    z_valid = df["z_tp"].dropna()
    print(model.report(df["z0"].to_numpy()), flush=True)
    cv = model.cross_validate()
    print(f"uncertainty: {cv}", flush=True)
    print(
        f"z_tp (m)   : [{z_valid.min():.2f}, {z_valid.max():.2f}] "
        f"mean {z_valid.mean():.2f}  ({z_valid.size:,} valued, "
        f"{df['z_tp'].isna().sum():,} NaN=L/HHW)",
        flush=True,
    )

    # Z0 is IDW-interpolated from the JMA/JCG Kanto-South tide-station network,
    # which spans Tokyo Bay, Sagami/Suruga Bay, the Izu Peninsula and Izu Islands.
    # Report the fraction of points outside its footprint (approximate Z0 there).
    pad = 0.10
    glon, glat = model.lon, model.lat
    outside = ~(
        (df["lon"] >= glon.min() - pad)
        & (df["lon"] <= glon.max() + pad)
        & (df["lat"] >= glat.min() - pad)
        & (df["lat"] <= glat.max() + pad)
    )
    n_out = int(outside.sum())
    frac_out = n_out / len(df) if len(df) else 0.0
    z0_validity = (
        f"Z0 = T.P. - chart datum (基本水準面), IDW from {len(glon)} JMA/JCG "
        f"tide stations (lon [{glon.min():.2f},{glon.max():.2f}], "
        f"lat [{glat.min():.2f},{glat.max():.2f}]); "
        f"{n_out:,} points ({frac_out:.1%}) lie outside the network footprint "
        f"(far offshore SE, deep water where Z0 is immaterial)."
    )
    print(f"z0 validity: {z0_validity}", flush=True)

    # Optional ellipsoidal branch: z_ell = z_tp + N (GSI geoid). NaN where the
    # geoid is undefined (open ocean) or z_tp is NaN (L/HHW marks).
    columns = ["mark", "lon", "lat", "z_tp", "depth_cd", "z0", "unit", "geodetic"]
    geoid_attr = None
    if args.geoid is not None:
        geoid_path = (
            config.geoid_file() if str(args.geoid) == "__default__" else args.geoid
        )
        geoid = GeoidModel.from_gsigeo_asc(geoid_path)
        n = geoid.height(df["lon"].to_numpy(), df["lat"].to_numpy())
        df["z_ell"] = df["z_tp"].to_numpy() + n
        columns.insert(4, "z_ell")
        defined = int(np.isfinite(df["z_ell"]).sum())
        geoid_attr = (
            f"z_ell = z_tp + N (GSI geoid {geoid_path.name}); {defined:,} defined"
        )
        print(
            f"z_ell (m)  : geoid N from {geoid_path.name}; "
            f"{defined:,}/{len(df):,} defined "
            f"({df['z_ell'].isna().sum():,} NaN=open-ocean geoid / L marks)",
            flush=True,
        )

    # column order: identity + primary result first, provenance after
    df = df[columns]

    attrs = {
        "title": "M7001 bathymetry converted to Tokyo Peil (T.P.)",
        "source": _SOURCE_LABEL,
        "source_file": str(source),
        "vertical_datum": "Tokyo Peil (T.P. / 東京湾平均海面)",
        "vertical_convention": "z_tp = elevation (m), positive up; seabed negative",
        "z0_definition": (
            "Z0 = T.P. - chart datum (基本水準面 = 略最低低潮面); "
            "z_tp(N) = -(depth_cd + Z0). Z0 from JMA/JCG tide-station datums "
            "(harmonic z0 + JMA 潮位表基準面), NOT gauge observation datum (DL)."
        ),
        "z0_table": str(z0_table),
        "z0_interpolation": f"{args.method}"
        + (f" (IDW power {args.z0_power})" if args.method == "idw" else ""),
        "z0_uncertainty": f"leave-one-out CV RMS {cv.rms * 100:.1f} cm "
        f"(MAE {cv.mae * 100:.1f}, max {cv.max_abs * 100:.1f} cm; n={cv.n})",
        "z0_validity": z0_validity,
        "marks": ",".join(args.marks),
        "generated_by": "topobathy topobathy-m7001-to-tp",
    }
    if geoid_attr is not None:
        attrs["ellipsoidal_height"] = geoid_attr

    out_base = out_dir / args.out_name
    written = write_points(df, out_base, formats=args.formats, attrs=attrs)
    print("wrote:", flush=True)
    for path in written:
        print(f"  {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
