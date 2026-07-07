# Vertical datum conversion — chart datum ⇄ T.P. ⇄ ellipsoid (Japan-wide)

A general, nationwide method for converting bathymetry/topography between the
nautical **chart datum** (基本水準面 ≈ 略最低低潮面), the national height datum
**T.P.** (東京湾平均海面 / 標高), and the **WGS84 ellipsoid**. It follows the Japan
Coast Guard's ellipsoidally-referenced-survey (ERS, 楕円体基準水深測量) method
(Okubo et al. 2022 — Tokyo Bay; Shiozawa et al. 2023 — Japan Sea).

Implemented by [`topobathy.datum.SeparationModel`](../topobathy/datum/separation.py)
(+ [`GeoidModel`](../topobathy/datum/geoid.py)). Not specific to M7001 / Tokyo Bay —
drive it with tide stations covering **any** Japanese area of interest.

## The method: a continuous separation surface

The chart datum is a spatially-varying *tidal* surface; a geodetic datum (T.P.,
ellipsoid) is a *level/reference* surface. The scientifically correct conversion
models the **separation** between them as a continuous field, rather than applying
a single constant. Three components (all functions of position):

| symbol | quantity | source |
|---|---|---|
| `Z0(x,y)` | 平均水面 − 基本水準面 (tidal range term) | JCG harmonic constants (`Z0 = Hm2+Hs2+Hk1+Ho1`) / 海保 **Z0区分図** |
| `ζ_MSL(x,y)` | height of local mean sea level above T.P. (≈ sea-surface topography) | tide-gauge 平均水面 / MDT model (small, cm-level) |
| `N(x,y)` | geoid height above the ellipsoid | **GSI「日本のジオイド2011」** |

give the separations

```
(T.P. − 基本水準面)(x,y) = Z0(x,y) − ζ_MSL(x,y)          # tide-station data only
最低水面の標高 H_CD(x,y)  = −(T.P. − 基本水準面)            # chart datum in T.P. (標高)
最低水面の楕円体高        = N(x,y) + H_CD(x,y)              # + GSI geoid (for GNSS/ERS)
```

and the depth conversion (chart-datum depth positive-down; `z_tp` = elevation, +up):

```
depth_TP(x,y) = depth_CD(x,y) + (T.P. − 基本水準面)(x,y)
z_tp          = − depth_TP
```

This mirrors the JCG ERS "最低水面モデル" construction (Shiozawa et al. 2023, Figs
4–5): 平均水面モデル = 平均水面高度 (ζ_MSL) + ジオイド (N); 最低水面モデル = 平均水面
モデル − Z0. Internationally the same separation-surface approach underlies NOAA
**VDatum**, the UK **VORF**, the Netherlands **NEVREF** and Australia's
**AUSHYDROID**.

> **Note — T.P. vs ellipsoid.** Converting to **T.P.** needs only tide-station
> data (`Z0 − ζ_MSL`); the geoid cancels. The geoid `N` is required **only** for
> the **ellipsoidal** branch (GNSS-referenced surveying). So M7001 → T.P. runs
> without any geoid file.

## How topobathy implements it

1. **Tide-station datum table** — `lon, lat, tp_minus_cd_m` (= `T.P. − 基本水準面`).
   - **Nationwide, authoritative:** `topobathy/data/japan_tide_datums_jcg.csv`
     (**~1000 gazetted ports**) — the official JCG「平均水面、最高水面及び最低水面
     一覧表」, parsed by [`scripts/parse_jcg_datum_table.py`](../scripts/parse_jcg_datum_table.py)
     (word-position PDF extraction; no transcription). Each port carries the
     official `z0_msl_m` (平均水面下 Z0 = MSL − 基本水準面) and, for GNSS-surveyed
     ports, `cd_ellipsoidal_m` (最低水面の楕円体高, GRS80). This is the "Z0区分図"
     authority in tabular form, usable anywhere in Japan.
   - **M7001 region:** `topobathy/data/kanto_south_tp_minus_cd.csv` (**85 stations**),
     built by [`scripts/build_z0_table.py`](../scripts/build_z0_table.py) = the JCG
     一覧表 ports for Kanto-South (`tp = z0_msl − ζ_MSL`) with exact
     **JMA 潮位表基準面** anchors (Suruga Bay / Izu Islands / NE Pacific, where ζ_MSL
     departs from ~0.03 m).
   - Any region: `scripts/fetch_jma_tide_datums.py` reads `潮位表基準面の標高`
     (= `−(T.P. − 基本水準面)`) per JMA station code from the JMA tidal database.
2. **`SeparationModel`** interpolates the separation to a continuous surface, a
   grid (the "最低水面モデル"), or scattered points:
   ```python
   from topobathy import SeparationModel
   model = SeparationModel.from_csv("my_region_datums.csv", method="linear")
   z0   = model.interpolate(lon, lat)             # T.P. − chart datum
   d_tp = model.depth_to_tp(depth_cd, lon, lat)   # chart-datum depth -> T.P. depth
   lonc, latc, grid = model.grid((138,141,34,36), dlon=1.5/60, dlat=1/60)  # 最低水面モデル
   cv = model.cross_validate()                    # leave-one-out uncertainty
   ```
   Interpolation `method`: **`linear`** (TIN/Delaunay barycentric — the JCG method,
   and the most accurate here; IDW fallback outside the hull), `idw` (robust, no
   overshoot), `cubic`, or `tps` (thin-plate-spline RBF).
3. **`GeoidModel`** — the **ellipsoidal branch**. Download the GSI geoid
   「日本のジオイド2011」once with
   [`scripts/get_gsigeo.py`](../scripts/get_gsigeo.py) (direct, no login →
   `$DATA_DIR/geoid/gsigeo2011_ver2_2.asc`); then a T.P. height plus the geoid `N`
   gives the WGS84 ellipsoidal height:
   ```python
   from topobathy import config, GeoidModel
   geoid = GeoidModel.from_gsigeo_asc(config.geoid_file())   # 1801×1201 grid, bilinear
   h_ell = model.chart_datum_ellipsoidal_height(lon, lat, geoid)   # 最低水面の楕円体高
   ```
   `topobathy-m7001-to-tp --geoid` adds a `z_ell` (= `z_tp + N`) column to the
   soundings; `topobathy-build-datum-model --geoid` adds a `chart_datum_ellipsoidal`
   grid variable. **Coverage:** GSIGEO2011 is defined over land + coastal seas
   (Tokyo Bay ~fully; `z_ell` there is complete) but not the open ocean (the
   deep-Pacific SE of the sheet is undefined → `z_ell` NaN). **Accuracy:** ~cm on
   land/coast; the GSI marine geoid carries ~0.1 m uncertainty over the sea (GSI is
   refining it via airborne gravimetry). Cross-checking the geoid-derived
   最低水面の楕円体高 against the official 一覧表 `cd_ellipsoidal_m` (341 ports) agrees
   to ~0.1 m mean — consistent with that marine-geoid limit and the steep Kanto
   geoid gradient (~0.5 m/0.1°). **The T.P. product (RMS 6.3 cm) is geoid-
   independent and remains primary;** `z_ell` is the optional GNSS/ERS layer.
4. **Continuous grid deliverable** — `topobathy-build-datum-model` writes the
   "最低水面モデル" as NetCDF (JCG 1′×1.5′ grid; `tp_minus_cd`,
   `chart_datum_elevation`, optional `chart_datum_ellipsoidal`) for a region, the
   way JCG builds a model then applies it to soundings.

## Accuracy — this implementation

The M7001 → T.P. product uses **`linear` (TIN)** over the **85-station** JCG
一覧表 + JMA network — the JCG ERS interpolation. **Leave-one-out cross-validation**
(drop each station, predict from the rest) gives the interpolation uncertainty:

| network | method | RMS | MAE |
|---|---|---:|---:|
| **85 (JCG 一覧表 + JMA, used)** | **linear (TIN)** | **6.3 cm** | 3.4 cm |
| 46 (harmonic + JMA) | linear | 7.1 cm | 3.5 cm |
| 85 | idw (p=2) | 8.x cm | ~5 cm |

RMS ~6 cm is consistent with the JCG-reported ~0.05–0.10 m ERS accuracy (Shiozawa
et al. 2023) and within IHO **S-44** special order. (The max ~36 cm is a single
isolated station under leave-one-out; the working error is the ~3 cm MAE.) Each
product's sidecar records its own CV numbers.

### Remaining refinements toward the absolute-most-rigorous field

- **Z0(x,y)** now comes from the **official 海保 一覧表** (`z0_msl_m`) for every
  gazetted port — the authoritative Z0. The remaining approximation is horizontal
  **interpolation between ports**; a coastline/hydrodynamics-aware scheme (NOAA
  **TCARI**, Laplace-weighted; or a tidal-model field) would avoid interpolating
  across land, though TIN already respects the station Delaunay.
- **ζ_MSL** is exact where a JMA 潮位表基準面 anchor exists (Suruga/Izu/NE); for the
  Tokyo-Bay JCG ports it uses `MSL − T.P. ≈ 0.03 m` (validated; few-cm residual).
  The **exact, ζ_MSL-free** route is the official `cd_ellipsoidal_m` (最低水面の
  楕円体高) minus a **GSI geoid** — both authoritative — giving the chart datum's
  T.P. 標高 directly (`GeoidModel` + `scripts/get_gsigeo.py`).
- Japanese chart datum is 略最低低潮面 (`Z0 = Hm2+Hs2+Hk1+Ho1`), a defined
  approximation to the international **LAT** (lowest astronomical tide, the minimum
  of an ≥18.6-year tidal prediction); the two differ by a few cm.

## References

- 塩澤舞香ほか (2023) 日本沿岸域における楕円体基準水深測量の標準手順確立に向けて(2)，海洋
  情報部研究報告 61 — [PDF](https://www1.kaiho.mlit.go.jp/kenkyu/report/rhr61/rhr61t_t_03.pdf)
  (基礎: 大久保ほか 2022, 東京湾).
- 海上保安庁「[平均水面、最高水面及び最低水面の高さ](https://www1.kaiho.mlit.go.jp/TIDE/datum/)」(Z0区分図) ／
  「[潮汐調和定数](https://www1.kaiho.mlit.go.jp/TIDE/harmonic/)」
- 気象庁「[潮位表](https://www.data.jma.go.jp/kaiyou/db/tide/suisan/)」(潮位表基準面の標高) ／
  「[用語集](https://www.data.jma.go.jp/kaiyou/db/tide/knowledge/tide/yougo.html)」
- 国土地理院「[日本のジオイド2011](https://www.gsi.go.jp/buturisokuchi/grageo_geoidseika.html)」
- NOAA [VDatum](https://vdatum.noaa.gov/) ／ TCARI: Hess et al.,
  [NOAA Tech. Report NOS CS 4](https://repository.library.noaa.gov/view/noaa/1689)
- UK [VORF](https://www.ucl.ac.uk/engineering/civil-environmental-geomatic-engineering/research/groups-centres-and-sections/vertical-offshore-reference-frames-vorf)
  (Iliffe/Ziebart) ／ Slobbe et al. (2018) NEVREF ／
  [AUSHYDROID](https://www.tandfonline.com/doi/full/10.1080/01490419.2024.2305898)
- Tidal datums + uncertainty: [Modeling Tidal Datums… (JMSE 2019)](https://www.mdpi.com/2077-1312/7/2/44)
