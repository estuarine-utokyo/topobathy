"""CLI: draw M7001 depth contour maps (chart datum, T.P., and their difference).

Reads a T.P.-converted M7001 point product (from ``topobathy-m7001-to-tp``) and
renders three filled-contour maps of the depth-carrying ``N`` marks:

1. ``*_depth_chartdatum.png`` — original depth below **chart datum** (基本水準面).
2. ``*_depth_tp.png``         — depth below **T.P.** (= chart-datum depth + Z0).
3. ``*_depth_diff_z0.png``    — the difference (T.P. − chart datum) = the applied
   spatially-varying datum correction ``Z0``.

Maps 1 and 2 look nearly identical (Z0 is a ~1–2 m shift on depths of up to
hundreds of metres); map 3 isolates the correction and reveals the Z0 field
growing toward the inner bay. Coastline (``L``) / low-tide (``M``) marks are
overlaid in grey for geographic context (no basemap dependency).

Heavy for dense sheets — run as a batch job (``scripts/genkai_plot_m7001_tp.sh``).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from topobathy import config  # noqa: E402
from topobathy.io import read_points  # noqa: E402
from topobathy.plot import GriddedField, grid_scatter  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="topobathy-plot-m7001-tp",
        description="Contour maps of M7001 depth: chart datum, T.P., and difference.",
    )
    p.add_argument(
        "--tp-product",
        type=Path,
        default=None,
        help="T.P. product parquet/csv (default: $DATA_DIR/.../TP/M7001_TP_tokyobay.parquet)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs/figures"),
        help="output directory for the PNGs (default: docs/figures)",
    )
    p.add_argument(
        "--prefix", default="m7001", help="output filename prefix (default: m7001)"
    )
    p.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        default=None,
        metavar=("LON_MIN", "LON_MAX", "LAT_MIN", "LAT_MAX"),
        help="plot window (default: extent of the N points, padded)",
    )
    p.add_argument("--nlon", type=int, default=420, help="grid columns (default: 420)")
    p.add_argument("--nlat", type=int, default=480, help="grid rows (default: 480)")
    p.add_argument(
        "--mask-km",
        type=float,
        default=2.5,
        help="blank grid cells farther than this (km) from data (default: 2.5)",
    )
    p.add_argument("--dpi", type=int, default=150, help="figure DPI (default: 150)")
    return p


def _draw(
    field: GriddedField,
    *,
    title: str,
    cbar_label: str,
    cmap: str,
    levels: np.ndarray,
    extend: str,
    coast_lon: np.ndarray,
    coast_lat: np.ndarray,
    out_png: Path,
    dpi: int,
) -> None:
    lat0 = float(np.mean(field.lat))
    fig, ax = plt.subplots(figsize=(8.2, 8.0))
    cf = ax.contourf(
        field.lon, field.lat, field.values, levels=levels, cmap=cmap, extend=extend
    )
    ax.contour(
        field.lon,
        field.lat,
        field.values,
        levels=levels[:: max(1, len(levels) // 8)],
        colors="k",
        linewidths=0.3,
        alpha=0.35,
    )
    if coast_lon.size:
        ax.scatter(coast_lon, coast_lat, s=0.05, c="0.35", alpha=0.5, linewidths=0)
    ax.set_aspect(1.0 / np.cos(np.radians(lat0)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title(title)
    cbar = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label(cbar_label)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_png}", flush=True)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    product = args.tp_product
    if product is None:
        product = config.m7001_tp_dir() / "M7001_TP_tokyobay.parquet"
    print(f"product: {product}", flush=True)
    df = read_points(product)

    is_n = df["mark"].to_numpy() == "N"
    n = df.loc[is_n]
    coast = df.loc[df["mark"].isin(["L", "M"])]
    if n.empty:
        print("ERROR: no N (depth) marks in the product.", flush=True)
        return 1

    lon = n["lon"].to_numpy()
    lat = n["lat"].to_numpy()
    depth_cd = n["depth_cd"].to_numpy()  # metres below chart datum
    z0 = n["z0"].to_numpy()  # T.P. - chart datum (m)

    if args.bbox is not None:
        bbox = tuple(args.bbox)
    else:
        pad = 0.02
        bbox = (lon.min() - pad, lon.max() + pad, lat.min() - pad, lat.max() + pad)
    print(
        f"N points: {len(n):,}  bbox: {tuple(round(b, 3) for b in bbox)}  "
        f"depth_cd [{depth_cd.min():.1f},{depth_cd.max():.1f}] m",
        flush=True,
    )

    # Grid the chart-datum depth and the Z0 correction; T.P. depth = sum of the two,
    # so the difference map is exactly the gridded Z0 (self-consistent).
    g_cd = grid_scatter(
        lon, lat, depth_cd, bbox, nlon=args.nlon, nlat=args.nlat, mask_km=args.mask_km
    )
    g_z0 = grid_scatter(
        lon, lat, z0, bbox, nlon=args.nlon, nlat=args.nlat, mask_km=args.mask_km
    )
    g_tp = GriddedField(lon=g_cd.lon, lat=g_cd.lat, values=g_cd.values + g_z0.values)

    coast_lon = coast["lon"].to_numpy()
    coast_lat = coast["lat"].to_numpy()

    # Bathymetric (non-uniform) depth levels: dense in the shallow range so the
    # bay-interior structure (<~70 m) is resolved, coarser for the deep bay mouth /
    # Sagami-Suruga corners. Clipped to just above the data maximum.
    bathy_levels = np.array(
        [
            0,
            2,
            5,
            10,
            15,
            20,
            25,
            30,
            40,
            50,
            60,
            80,
            100,
            150,
            200,
            300,
            400,
            500,
            700,
            1000,
            1400,
            1800,
        ],
        dtype=float,
    )
    dmax = float(np.nanmax(g_cd.values))
    idx = int(np.searchsorted(bathy_levels, dmax))
    depth_levels = bathy_levels[: min(idx + 1, len(bathy_levels))]

    _draw(
        g_cd,
        title="M7001 depth — chart datum (lowest water)",
        cbar_label="depth below chart datum (m)",
        cmap="turbo",
        levels=depth_levels,
        extend="max",
        coast_lon=coast_lon,
        coast_lat=coast_lat,
        out_png=args.out_dir / f"{args.prefix}_depth_chartdatum.png",
        dpi=args.dpi,
    )
    _draw(
        g_tp,
        title="M7001 depth — Tokyo Peil (T.P.)",
        cbar_label="depth below T.P. (m)",
        cmap="turbo",
        levels=depth_levels,
        extend="max",
        coast_lon=coast_lon,
        coast_lat=coast_lat,
        out_png=args.out_dir / f"{args.prefix}_depth_tp.png",
        dpi=args.dpi,
    )

    zmin = float(np.floor(np.nanmin(g_z0.values) * 10) / 10)
    zmax = float(np.ceil(np.nanmax(g_z0.values) * 10) / 10)
    z0_levels = np.linspace(zmin, zmax, 19)
    _draw(
        g_z0,
        title="M7001 datum correction — T.P. depth − chart-datum depth (= Z0)",
        cbar_label="Z0 = T.P. − chart datum (m)",
        cmap="YlOrRd",
        levels=z0_levels,
        extend="neither",
        coast_lon=coast_lon,
        coast_lat=coast_lat,
        out_png=args.out_dir / f"{args.prefix}_depth_diff_z0.png",
        dpi=args.dpi,
    )
    print("done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
