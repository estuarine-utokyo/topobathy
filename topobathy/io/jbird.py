"""Reader for the JHA / Japan Coast Guard **J-BIRD** fixed-column bathymetry format.

The J-BIRD (財団法人日本水路協会「海底地形デジタルデータ」) products — e.g. **M7001**
(Southern Kanto / 関東南部) — store vector bathymetry as FORTRAN fixed-column ASCII
records, one point per line. Each point is tagged by a one-character *mark*:

======  ==================================================================
 mark    meaning
======  ==================================================================
 ``L``   coastline point, at 略最高高潮面 (approx. HHW, highest high water)
 ``M``   low-tide-line point, at 基本水準面 (**chart datum** ≈ LLW)
 ``N``   depth-contour point; carries a **depth below chart datum**
 ``A``   figure-frame corner (structural, no survey value)
 ``B``   grid point (structural, no survey value)
======  ==================================================================

Column layout (1-indexed, from the bundled ``help/データの概要/format.htm`` spec):

===========  =====  ===============================================================
 columns      fmt    field
===========  =====  ===============================================================
 1            A1     mark
 11–17        F7.1   vertical value (depth below chart datum for N; 0.0 for L/M)
 18–26        F9.5   latitude  (geodetic, datum in col 60)
 27–36        F10.5  longitude (geodetic, datum in col 60)
 48–50        A3     vertical unit: ``MET`` metre / ``FAT`` fathom
 60           I1     geodetic datum: 1 = WGS84, 2 = Tokyo datum, 3 = unknown
 75–80        A6     sheet code (source chart identifier)
===========  =====  ===============================================================

For M7001 (Southern Kanto, Ver. 2.4) the whole file is unit ``MET`` and datum
WGS84 (col 60 = 1). See ``$DATA_DIR/bathymetry/M7001/README.md`` for the full spec.

The reader returns a canonical :class:`pandas.DataFrame` with columns
``mark, lon, lat, depth_cd, unit, geodetic`` (``depth_cd`` = the raw vertical
value = metres below chart datum). Records are fixed width, so when every record
has the same byte length the whole file is parsed vectorised via NumPy (fast even
for the ~3.95 M-point M7001 sheet); otherwise a robust line-by-line fallback runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from numpy.typing import NDArray

__all__ = ["JBIRD_COLSPECS", "BBox", "read_jbird"]

# 0-indexed [start, stop) byte slices for the J-BIRD record fields.
JBIRD_COLSPECS: dict[str, tuple[int, int]] = {
    "mark": (0, 1),
    "depth_cd": (10, 17),  # vertical value, F7.1 — metres below chart datum (N)
    "lat": (17, 26),  # F9.5, degrees
    "lon": (26, 36),  # F10.5, degrees
    "unit": (47, 50),  # A3, 'MET' / 'FAT'
    "geodetic": (59, 60),  # I1, 1=WGS84 2=Tokyo 3=unknown
}

# Marks that carry a usable survey position (L/M/N). A/B are structural.
SURVEY_MARKS: tuple[str, ...] = ("L", "M", "N")

# Canonical output schema — enforced on BOTH the fast and fallback parse paths so
# they return byte-for-byte identical DataFrames.
_CANONICAL_DTYPES: dict[str, str] = {
    "mark": "str",
    "lon": "float64",
    "lat": "float64",
    "depth_cd": "float64",
    "unit": "str",
    "geodetic": "int8",
}

# Source-file encoding. The numeric/mark columns are pure ASCII; Japanese text
# only appears in the separate 地名.txt gazetteer, never in the data records.
_ENCODING = "cp932"


@dataclass(frozen=True)
class BBox:
    """Geographic bounding box in degrees (inclusive)."""

    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

    def contains(
        self, lon: NDArray[np.float64], lat: NDArray[np.float64]
    ) -> NDArray[np.bool_]:
        return (
            (lon >= self.lon_min)
            & (lon <= self.lon_max)
            & (lat >= self.lat_min)
            & (lat <= self.lat_max)
        )


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Cast to the canonical schema so both parse paths agree exactly."""
    return df.astype(_CANONICAL_DTYPES)


def _detect_record_length(raw: bytes) -> int | None:
    """Return the fixed record length (incl. line terminator) or None if ragged."""
    nl = raw.find(b"\n")
    if nl < 0:
        return None
    reclen = nl + 1
    return reclen if len(raw) % reclen == 0 else None


def _col_float(block: NDArray[np.uint8], start: int, stop: int) -> NDArray[np.float64]:
    """Vectorised parse of a fixed-width numeric byte column to float64."""
    sub = np.ascontiguousarray(block[:, start:stop])
    return sub.view(f"S{stop - start}").astype(np.float64).ravel()


def _col_str(block: NDArray[np.uint8], start: int, stop: int) -> NDArray[np.str_]:
    """Vectorised parse of a fixed-width byte column to (stripped) str."""
    sub = np.ascontiguousarray(block[:, start:stop])
    return np.char.strip(np.char.decode(sub.view(f"S{stop - start}").ravel(), "ascii"))


def _read_fast(raw: bytes, reclen: int, marks: tuple[str, ...]) -> pd.DataFrame:
    """Vectorised fixed-record parse. Filters by mark *before* numeric parsing."""
    block = np.frombuffer(raw, dtype=np.uint8).reshape(-1, reclen)
    mark_codes = block[:, JBIRD_COLSPECS["mark"][0]]
    keep = np.zeros(block.shape[0], dtype=bool)
    for m in marks:
        keep |= mark_codes == ord(m)
    block = block[keep]

    cols: dict[str, NDArray[Any]] = {}
    marks_arr = _col_str(block, *JBIRD_COLSPECS["mark"])
    cols["mark"] = marks_arr
    cols["lon"] = _col_float(block, *JBIRD_COLSPECS["lon"])
    cols["lat"] = _col_float(block, *JBIRD_COLSPECS["lat"])
    cols["depth_cd"] = _col_float(block, *JBIRD_COLSPECS["depth_cd"])
    cols["unit"] = _col_str(block, *JBIRD_COLSPECS["unit"])
    cols["geodetic"] = _col_float(block, *JBIRD_COLSPECS["geodetic"]).astype(np.int8)
    return _finalize(pd.DataFrame(cols))


def _read_fallback(
    raw: bytes, marks: tuple[str, ...], max_records: int | None = None
) -> pd.DataFrame:
    """Robust line-by-line parse for ragged (non-fixed-length) files."""
    want = set(marks)
    rows: list[tuple[str, float, float, float, str, int]] = []
    for scanned, line in enumerate(
        raw.decode(_ENCODING, errors="replace").splitlines()
    ):
        if max_records is not None and scanned >= max_records:
            break
        if not line or line[0] not in want:
            continue
        try:
            depth = float(line[slice(*JBIRD_COLSPECS["depth_cd"])])
            lat = float(line[slice(*JBIRD_COLSPECS["lat"])])
            lon = float(line[slice(*JBIRD_COLSPECS["lon"])])
            geod = int(line[slice(*JBIRD_COLSPECS["geodetic"])] or "0")
        except ValueError:
            continue
        unit = line[slice(*JBIRD_COLSPECS["unit"])].strip()
        rows.append((line[0], lon, lat, depth, unit, geod))
    return _finalize(
        pd.DataFrame(
            rows, columns=["mark", "lon", "lat", "depth_cd", "unit", "geodetic"]
        )
    )


def read_jbird(
    path: str | Path,
    marks: Iterable[str] | None = None,
    bbox: BBox | None = None,
    max_records: int | None = None,
) -> pd.DataFrame:
    """Read a J-BIRD fixed-column bathymetry file into a canonical DataFrame.

    Parameters
    ----------
    path
        Path to the J-BIRD ASCII file (e.g. the M7001 sheet).
    marks
        Iterable of one-character marks to keep. Defaults to the survey marks
        ``("L", "M", "N")`` (frame/grid A/B points are dropped).
    bbox
        Optional geographic bounding box; only points inside it are returned.
    max_records
        If set, scan only the first ``max_records`` records of the file
        (useful for a quick preview / smoke test on the login node).

    Returns
    -------
    pandas.DataFrame
        Columns ``mark`` (str), ``lon``/``lat`` (float64, degrees),
        ``depth_cd`` (float64, metres below chart datum; 0.0 for L/M),
        ``unit`` (str), ``geodetic`` (int8).
    """
    path = Path(path)
    marks_t = tuple(marks) if marks is not None else SURVEY_MARKS
    if not marks_t:
        raise ValueError("`marks` is empty — nothing to read.")

    raw = path.read_bytes()
    reclen = _detect_record_length(raw)
    if reclen is not None and reclen > 1:
        if max_records is not None:
            raw = raw[: max_records * reclen]
        df = _read_fast(raw, reclen, marks_t)
    else:
        df = _read_fallback(raw, marks_t, max_records)

    if bbox is not None:
        mask = bbox.contains(df["lon"].to_numpy(), df["lat"].to_numpy())
        df = df.loc[mask].reset_index(drop=True)

    return df
