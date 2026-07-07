"""Tests for the J-BIRD fixed-column reader."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from topobathy.io import BBox, read_jbird


def _make_record(mark: str, depth: float, lat: float, lon: float) -> str:
    """Build one 80-char J-BIRD record (fields at the spec byte offsets)."""
    line = [" "] * 80
    line[0] = mark
    line[10:17] = f"{depth:7.1f}"
    line[17:26] = f"{lat:9.5f}"
    line[26:36] = f"{lon:10.5f}"
    line[47:50] = "MET"
    line[59] = "1"
    line[74:79] = "M7001"
    return "".join(line)


def _write_fixture(tmp_path: Path) -> Path:
    records = [
        _make_record("L", 0.0, 35.8807, 140.7373),
        _make_record("M", 0.0, 35.1456, 138.6958),
        _make_record("N", 12.5, 35.5000, 139.9000),
        _make_record("N", 1.0, 34.5909, 138.2234),
        _make_record("A", 0.0, 0.0, 0.0),  # frame point — dropped by default
    ]
    # CRLF-terminated fixed records, as in the real M7001 file
    raw = "\r\n".join(records) + "\r\n"
    path = tmp_path / "jbird_sample.dat"
    path.write_bytes(raw.encode("cp932"))
    return path


def test_read_default_marks_drops_frame(tmp_path: Path) -> None:
    df = read_jbird(_write_fixture(tmp_path))
    assert list(df["mark"]) == ["L", "M", "N", "N"]  # A dropped
    assert df["unit"].eq("MET").all()
    assert df["geodetic"].eq(1).all()


def test_values_parsed_at_correct_offsets(tmp_path: Path) -> None:
    df = read_jbird(_write_fixture(tmp_path), marks=["N"])
    n0 = df.iloc[0]
    assert n0["mark"] == "N"
    assert np.isclose(n0["depth_cd"], 12.5)
    assert np.isclose(n0["lat"], 35.5000)
    assert np.isclose(n0["lon"], 139.9000)


def test_bbox_filter(tmp_path: Path) -> None:
    bbox = BBox(lon_min=139.0, lon_max=141.0, lat_min=35.0, lat_max=36.0)
    df = read_jbird(_write_fixture(tmp_path), bbox=bbox)
    # L (140.7,35.9) and N (139.9,35.5) are inside; M and the western N are out
    assert set(df["mark"]) == {"L", "N"}
    assert len(df) == 2


def test_max_records(tmp_path: Path) -> None:
    df = read_jbird(_write_fixture(tmp_path), max_records=2)
    assert list(df["mark"]) == ["L", "M"]


def test_fallback_matches_fast_path(tmp_path: Path) -> None:
    """A ragged file (variable line length) exercises the line-based fallback."""
    fixed = _write_fixture(tmp_path)
    df_fast = read_jbird(fixed)
    # append a shorter trailing comment-ish line -> not a multiple of reclen
    ragged = tmp_path / "ragged.dat"
    ragged.write_bytes(fixed.read_bytes() + b"short\r\n")
    df_slow = read_jbird(ragged)
    # the 'short' line starts with 's' -> not a survey mark, so results match
    assert df_fast.equals(df_slow)
