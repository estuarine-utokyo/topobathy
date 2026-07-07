"""topobathy — tools for building topo-bathymetric (DEM / bathymetry) datasets.

Sub-packages
------------
* :mod:`topobathy.io`     — dataset readers/writers (J-BIRD, point datasets).
* :mod:`topobathy.datum`  — vertical-datum conversions (chart datum <-> T.P.).
* :mod:`topobathy.utils`  — geospatial helpers.
* :mod:`topobathy.config` — ``$DATA_DIR``-based path resolution (portability).
* :mod:`topobathy.cli`    — command-line entry points.

Data locations are resolved through ``$DATA_DIR`` (see :mod:`topobathy.config`);
never hard-code absolute paths.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from topobathy.datum import (
    GeoidModel,
    SeparationModel,
    Z0Field,
    add_tp_elevation,
    chart_datum_to_tp_elevation,
)
from topobathy.io import BBox, read_jbird, read_points, write_points

try:
    __version__ = version("topobathy")
except PackageNotFoundError:  # not installed (e.g. running from a source checkout)
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "BBox",
    "GeoidModel",
    "SeparationModel",
    "Z0Field",
    "add_tp_elevation",
    "chart_datum_to_tp_elevation",
    "read_jbird",
    "read_points",
    "write_points",
]
