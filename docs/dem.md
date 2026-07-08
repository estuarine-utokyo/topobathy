# Bathymetric DEM gridding — standard method (splines in tension)

Turning scattered/contour soundings into a regular **DEM** raster is a distinct step
from the vertical-datum conversion (see [`docs/vertical_datum.md`](vertical_datum.md)):
first convert depths to a common datum (T.P.), then grid.

topobathy grids with the **community-standard method: continuous-curvature splines
in tension** (Smith & Wessel 1990) via GMT `surface` — the algorithm behind GEBCO
and NOAA coastal DEMs. It is **smooth** (no TIN facets / gradient kinks) yet avoids
the overshoot of pure minimum-curvature, and it bridges digitised depth contours
**without the terracing** that TIN / nearest-neighbour produce on contour-derived
data such as M7001.

## Why this method (survey of standard practice)

| use | standard |
|---|---|
| International / research (GEBCO) | **splines in tension**, GMT `surface` (GEBCO Cook Book) |
| NOAA coastal topo-bathy DEMs (CUDEM) | splines in tension + hydro-flattening (MB-System/GMT/`waffles`) |
| Multibeam survey surface | **CUBE** (Calder & Mayer 2003; used by JCG ERS via CARIS) |
| Japanese official grids (JODC J-EGG500, JHA JTOPO30) | **TIN** from digitised soundings/contours |
| JMA (tsunami / storm surge) | uses existing grids (GEBCO / J-EGG / Cabinet-Office nested), no own method |

M7001 is **digitised depth contours** — the data type GEBCO/JTOPO rank lowest and
that suffers TIN terracing — so a tension spline (which crosses contours smoothly)
is the appropriate standard, over TIN.

## Pipeline (`topobathy.grid.grid_dem`, GMT via `pygmt`)

1. **`blockmedian`** — one median sounding per grid cell (robust decimation; removes
   redundancy/spikes, prevents aliasing).
2. **`surface`** — grid with a tension factor (~0.25–0.4 for bathymetry; `0.35`
   default). `coltypes="g"` → geographic metric, lon/lat grid.
3. **coverage mask** — blank cells farther than `mask_km` (default 2 km) from any
   sounding, so the grid is not extrapolated far into data gaps.
4. **hydro-flattening** — clip the DEM to water at the real **OSM coastline**
   (`land_geom`; via [`xcoast`](https://github.com/estuarine-utokyo/xcoast)), so land
   (incl. reclaimed land / artificial islands such as Haneda, 中央防波堤) is NaN and
   the water edge follows the true coast — not a distance buffer. OSM resolves
   reclaimed land that coarser coastlines (GSHHG) miss.

```python
from topobathy import grid_dem
from topobathy.grid import osm_land_geometry

region = (139.55, 140.30, 34.90, 35.75)
land = osm_land_geometry(region)                       # OSM land polygon (xcoast)
dem = grid_dem(lon, lat, z_tp, region=region, spacing=0.002, tension=0.35,
               mask_km=2.0, land_geom=land)             # xarray DataArray, T.P. (+up)
```

The OSM land mask needs the `xcoast` package plus the OSM shapefile extracts under
`$DATA_DIR/OSM/` (`land-polygons-split-4326`, geofabrik water); paths resolve via
`topobathy.config.osm_land_shp` / `osm_water_shp`. `topobathy-m7001-dem --no-land-mask`
falls back to the plain distance-coverage mask.

## Run

```bash
pjsub scripts/genkai_m7001_dem.sh          # Tokyo Bay DEM -> TP/M7001_dem_tokyobay.nc
# or directly:
topobathy-m7001-dem --region 139.55 140.30 34.90 35.75 --spacing 0.002 \
    --out $DATA_DIR/bathymetry/M7001/TP/M7001_dem_tokyobay.nc
```

Output: a CF NetCDF, variable `elevation` = seabed height above **T.P.** (m, +up;
seabed negative), NaN outside the coverage mask. Grids the `N` (depth-contour) and
`M` (low-tide-line) marks, which carry a T.P. elevation; `L` (HHW coastline) has no
depth and is excluded (it bounds the land side).

## Notes & refinements

- **Tension** trades smoothness vs. faithfulness; raise it (→0.4–0.5) if the spline
  overshoots into small positive elevations in shallow corners.
- **Hydro-flattening** clips the DEM to water at the **OSM coastline** (step 4); OSM
  captures reclaimed land / artificial islands that GSHHG or the M7001 `L` waterline
  may not. `--no-land-mask` reverts to the distance-coverage mask only.
- **Compositing** multiple sources (M7001 + CUDEM/GEBCO/SRTM15plus/… under
  `$DATA_DIR/bathymetry`) follows the same GEBCO/NOAA workflow: assemble by data
  priority → tension-spline grid → mask/flatten. This is the natural next tool.

## References

- Smith, W. H. F. & Wessel, P. (1990) *Gridding with continuous curvature splines
  in tension*, Geophysics 55(3). [doi:10.1190/1.1442837](https://doi.org/10.1190/1.1442837)
- IHO-IOC **GEBCO Cook Book**. <https://www.gebco.net/data-products/gebco-cook-book>
- NOAA **CUDEM** (Amante et al. 2023). <https://www.mdpi.com/2072-4292/15/6/1702>
- Calder, B. R. & Mayer, L. A. (2003) *Automatic processing of high-rate,
  high-density multibeam data* (**CUBE**), G-cubed 4(6).
- JODC **J-EGG500** / JHA **JTOPO30** (TIN-based Japanese grids).
  <https://www.jodc.go.jp/jodcweb/JDOSS/infoJEGG_j.html>
