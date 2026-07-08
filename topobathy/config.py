"""Environment / path resolution shared across topobathy tools.

Portability rule (see the repo README and the global HPC rules): data locations
are resolved through the ``$DATA_DIR`` environment variable, never hard-coded
absolute paths. ``$DATA_DIR`` is a *group-shared* directory (e.g.
``/home/pj24001722/share/Data``) that is not under ``$HOME``, so it must come
from the environment. Missing required env vars fail loudly rather than falling
back to a machine-specific guess.
"""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

__all__ = [
    "get_data_dir",
    "get_bathymetry_dir",
    "m7001_source_file",
    "m7001_tp_dir",
    "default_z0_table",
    "geoid_file",
    "osm_land_shp",
    "osm_water_shp",
    "coastmask_cache_dir",
]


def get_data_dir() -> Path:
    """Return ``$DATA_DIR`` as a :class:`Path`, or raise if unset/nonexistent.

    ``$DATA_DIR`` points at the group-shared data root (``.../share/Data``). We
    fail loudly on a missing var so a job never silently writes to, or reads
    from, the wrong machine-local location.
    """
    raw = os.environ.get("DATA_DIR")
    if not raw:
        raise RuntimeError(
            "DATA_DIR is not set. Export it (batch jobs need '#PJM -X' so the "
            "login-shell environment is passed to the job) before running "
            "topobathy tools."
        )
    path = Path(raw)
    if not path.is_dir():
        raise RuntimeError(f"DATA_DIR points at a non-directory: {path}")
    return path


def get_bathymetry_dir() -> Path:
    """``$DATA_DIR/bathymetry`` — the root of all bathymetry source datasets."""
    return get_data_dir() / "bathymetry"


def m7001_source_file() -> Path:
    """Path to the JHA M7001 (Southern Kanto, Ver. 2.4) J-BIRD ASCII file.

    The dataset is documented in ``$DATA_DIR/bathymetry/M7001/README.md``.
    """
    return get_bathymetry_dir() / "M7001" / "ascii" / "M7001_関東南部_Ver.2.4"


def m7001_tp_dir() -> Path:
    """Output directory for the T.P.-converted M7001 products."""
    return get_bathymetry_dir() / "M7001" / "TP"


def default_z0_table() -> Path:
    """Path to the bundled Kanto-South tide-station datum table.

    ``tp_minus_cd_m = T.P. − 基本水準面`` at 45 JMA/JCG tide stations spanning Tokyo
    Bay, Sagami Bay, Suruga Bay, the Izu Peninsula and the Izu Islands (see
    ``docs/m7001.md`` for sources). Shipped as package data so the M7001
    conversion is self-contained; for other regions supply a nationwide table
    (see ``scripts/fetch_jma_tide_datums.py``) via the CLI (``--z0-table``).
    """
    with resources.as_file(
        resources.files("topobathy.data") / "kanto_south_tp_minus_cd.csv"
    ) as p:
        return Path(p)


def geoid_file() -> Path:
    """Path to the GSI geoid grid under ``$DATA_DIR/geoid/`` (newest GSIGEO2011).

    Not bundled (large); download once with ``scripts/get_gsigeo.py``. Only needed
    for the ellipsoidal-height branch of :class:`~topobathy.datum.geoid.GeoidModel`;
    the T.P. conversion itself does not use it.
    """
    geoid_dir = get_data_dir() / "geoid"
    candidates = sorted(geoid_dir.glob("gsigeo2011*.asc"), reverse=True)
    if not candidates:
        raise RuntimeError(
            f"No GSIGEO geoid grid in {geoid_dir}. Run scripts/get_gsigeo.py "
            "to download it (「日本のジオイド2011」)."
        )
    return candidates[0]


def osm_land_shp() -> Path:
    """OSM global land-polygons shapefile (``$DATA_DIR/OSM/...``) for the DEM land
    mask (via ``xcoast``). Download the OSMdata land-polygons-split-4326 extract."""
    return get_data_dir() / "OSM" / "land-polygons-split-4326" / "land_polygons.shp"


def osm_water_shp() -> Path:
    """Geofabrik OSM water-polygons shapefile used by ``xcoast`` to carve inland
    water out of the land mask (rivers/lakes stay 'not land')."""
    return get_data_dir() / "OSM" / "geofabrik_kanto" / "gis_osm_water_a_free_1.shp"


def coastmask_cache_dir() -> Path:
    """Cache directory for xcoast coastmask GeoPackages."""
    return get_data_dir() / "OSM" / "coastmask_cache"
