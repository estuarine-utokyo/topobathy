"""Tests for the point-dataset writer/reader round-trip."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from topobathy.io import read_points, write_points


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mark": ["N", "M"],
            "lon": [139.5, 139.6],
            "lat": [35.0, 35.1],
            "z_tp": [-11.5, -1.5],
        }
    )


def test_csv_parquet_roundtrip(tmp_path: Path) -> None:
    base = tmp_path / "pts"
    written = write_points(_df(), base, formats=("csv", "parquet"))
    names = {p.name for p in written}
    assert {"pts.csv", "pts.parquet"} <= names
    back = read_points(base.with_suffix(".parquet"))
    pd.testing.assert_frame_equal(back, _df())


def test_readme_sidecar_written(tmp_path: Path) -> None:
    base = tmp_path / "pts"
    write_points(_df(), base, formats=("csv",), attrs={"title": "unit test"})
    readme = base.with_suffix(".README.md")
    assert readme.exists()
    assert "unit test" in readme.read_text()


def test_unsupported_format_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError):
        write_points(_df(), tmp_path / "pts", formats=("geojson",))
