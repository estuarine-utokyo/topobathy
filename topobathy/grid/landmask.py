"""OSM-derived land geometry for DEM hydro-flattening (via the ``xcoast`` package).

Builds a single land (Multi)Polygon over a region from the OpenStreetMap land
polygons, so a bathymetric DEM can be clipped to the actual water body (rather than
a crude distance-from-data buffer). OSM resolves reclaimed land / artificial islands
(e.g. Haneda, 中央防波堤) that coarser coastlines (GSHHG) miss.

Requires the standalone ``xcoast`` package (OSM land masking) plus ``geopandas`` /
``shapely`` / ``pyogrio``, and the OSM shapefile extracts under ``$DATA_DIR/OSM/``
(see :func:`topobathy.config.osm_land_shp`). Install ``xcoast`` with
``pip install -e /path/to/xcoast`` (or ``git+https://github.com/estuarine-utokyo/xcoast.git``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

from topobathy.grid.dem import Region

__all__ = ["osm_land_geometry"]


def osm_land_geometry(
    region: Region,
    land_shp: str | Path | None = None,
    water_shp: str | Path | None = None,
    cache_dir: str | Path | None = None,
    force: bool = False,
    **config_kwargs: Any,
) -> "BaseGeometry":
    """Return the OSM land (Multi)Polygon over ``region`` = ``(W, E, S, N)``.

    Parameters mirror :class:`xcoast.CoastmaskConfig`; paths default to the
    ``$DATA_DIR/OSM`` extracts (:mod:`topobathy.config`). ``remove_orphan_islands``
    defaults to ``False`` here so small islands stay masked as land.
    """
    import xcoast

    from topobathy import config as _cfg

    conf = xcoast.CoastmaskConfig(
        land_shp_path=Path(land_shp) if land_shp else _cfg.osm_land_shp(),
        water_shp_path=Path(water_shp) if water_shp else _cfg.osm_water_shp(),
        cache_dir=Path(cache_dir) if cache_dir else _cfg.coastmask_cache_dir(),
        remove_orphan_islands=config_kwargs.pop("remove_orphan_islands", False),
        **config_kwargs,
    )
    w, e, s, n = region
    mask = xcoast.load((w, s, e, n), config=conf, force=force)  # xcoast bbox=(W,S,E,N)
    gdf = mask.land_gdf
    return gdf.union_all() if hasattr(gdf, "union_all") else gdf.unary_union
