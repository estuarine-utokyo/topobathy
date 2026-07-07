"""Write / read a canonical bathymetry point dataset (CSV / Parquet / NetCDF).

A "point dataset" is a :class:`pandas.DataFrame` of scattered soundings with, at
minimum, ``lon``/``lat`` and a value column. :func:`write_points` serialises it
to one or more formats plus a Markdown sidecar recording provenance so the output
directory is self-describing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

__all__ = ["SUPPORTED_FORMATS", "write_points", "read_points"]

SUPPORTED_FORMATS: tuple[str, ...] = ("csv", "parquet", "netcdf")

# float columns written with this precision in CSV (≈1 mm in degrees / metres)
_CSV_FLOAT_FMT = "%.6f"


def write_points(
    df: pd.DataFrame,
    out_base: str | Path,
    formats: Iterable[str] = ("csv", "parquet"),
    attrs: Mapping[str, str] | None = None,
    float_format: str = _CSV_FLOAT_FMT,
) -> list[Path]:
    """Serialise ``df`` to ``<out_base>.<ext>`` for each requested format.

    Parameters
    ----------
    df
        Point dataset.
    out_base
        Output path *without* extension (e.g. ``.../TP/M7001_TP``).
    formats
        Any subset of :data:`SUPPORTED_FORMATS`.
    attrs
        Optional provenance metadata; written to a ``<out_base>.README.md``
        sidecar and, for NetCDF, attached as global attributes.
    float_format
        printf-style format for CSV floats.

    Returns
    -------
    list[pathlib.Path]
        The files written.
    """
    out_base = Path(out_base)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    fmts = tuple(formats)
    unknown = set(fmts) - set(SUPPORTED_FORMATS)
    if unknown:
        raise ValueError(f"Unsupported format(s): {sorted(unknown)}")

    written: list[Path] = []
    for fmt in fmts:
        if fmt == "csv":
            path = out_base.with_suffix(".csv")
            df.to_csv(path, index=False, float_format=float_format)
        elif fmt == "parquet":
            path = out_base.with_suffix(".parquet")
            df.to_parquet(path, index=False)
        elif fmt == "netcdf":
            path = out_base.with_suffix(".nc")
            ds = df.to_xarray().rename({"index": "point"})
            if attrs:
                ds.attrs.update(attrs)
            ds.to_netcdf(path)
        written.append(path)

    if attrs:
        readme = out_base.with_suffix(".README.md")
        readme.write_text(_render_readme(out_base.name, df, attrs, written))
        written.append(readme)

    return written


def _render_readme(
    name: str,
    df: pd.DataFrame,
    attrs: Mapping[str, str],
    files: list[Path],
) -> str:
    lines = [f"# {name}", ""]
    for key, val in attrs.items():
        lines.append(f"- **{key}**: {val}")
    lines += [
        "",
        f"- **rows**: {len(df):,}",
        f"- **columns**: {', '.join(df.columns)}",
        f"- **files**: {', '.join(p.name for p in files)}",
        "",
    ]
    return "\n".join(lines)


def read_points(path: str | Path) -> pd.DataFrame:
    """Read a point dataset back, dispatching on file extension."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".parquet":
        return pd.read_parquet(path)
    if ext in (".nc", ".netcdf"):
        import xarray as xr

        return xr.open_dataset(path).to_dataframe().reset_index(drop=True)
    raise ValueError(f"Unrecognised point-dataset extension: {ext!r}")
