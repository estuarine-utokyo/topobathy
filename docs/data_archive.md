# Tokyo Bay data archive — what is where, and its state

The data live outside the repository, under `$DATA_DIR/geodata/bathymetry/` (group-shared,
licensed data: keep inside the group area). This page is the curated index; **`scripts/archive_status.py`**
(read-only, a few seconds) shows whether the disk still matches it (README present, newest file,
the DEM chain, the Sanbanze checksums). Updated 2026-11-14.

## Final products (what to use)

`M7001/TP/` (README: `M7001_dem_tokyobay.README.md` there; method: [`dem.md`](dem.md)):

| file | grid | contents |
|---|---|---|
| **`M7001_dem_tokyobay_50m.nc`** | 0.0005° (≈ 45 × 55 m) | M7001 + Chiba channel (Endo 2020) + Futtsu (JFA 2022) + Sanbanze (Chiba H28/H24); 2026-11-09 |
| **`M7001_dem_tokyobay_10m.nc`** | 0.0001° (≈ 9 × 11 m) | same sources; 2026-11-09 |
| `M7001_dem_futtsu_5m.nc` | 0.00005°, 139.77–139.83E 35.30–35.34N | Futtsu survey, nested in the 10 m DEM |

Stages kept for comparison and rollback (same grids): `*_m7001_only.nc` → `*_chiba_channel.nc` →
`*_futtsu.nc` → final. All DEMs are T.P., `elevation` +up, land = NaN. Known property: the
Sanbanze part is post-2011-earthquake and about 0.3 m deeper than the surrounding (older) M7001
([`sanbanze.md`](sanbanze.md)); M7001 itself carries no earthquake correction.

## Source datasets (Tokyo Bay related)

| directory | what | datum / grid | README | used by | state |
|---|---|---|---|---|---|
| `M7001/` | JHA/JCG chart soundings (Southern Kanto, Ver. 2.4) + `TP/` conversion and DEMs | chart datum → T.P. | yes (updated 2026-11-14) | everything | maintained; licensed ([`m7001.md`](m7001.md)) |
| `tokyo_bay/Futtsu_JFA_2023/` | Fisheries Agency 2022 survey, Futtsu flats, 0.5 m | T.P., EPSG:6677 | yes | `futtsu_jfa_merge.py` | maintained (moved here 2026-11-09) |
| `tokyo_bay/Sanbanze_Chiba_AP/` | Chiba Prefecture Sanbanze surveys, 8 epochs (S55–H28), 10 m and 100 m | A.P., zone IX (JGD2000/2011 unstated) | yes | `sanbanze_merge.py` | maintained; checksums in `sanbanze_chiba_ap.sha256`; spec: [`sanbanze.md`](sanbanze.md) |
| `tokyobay_endo/` | Endo (2020) 50 m Tokyo Bay edit (points, rasters, CAD/GIS, `…編集手順.docx`) | datum not stated (≈ M7001 − 0.98 m measured) | **no** | `endo50m_to_*.py`, Chiba channel | in use, **undocumented on disk**: no README, provenance only in [`dem.md`](dem.md) |
| `CAO_shutochokka_2025/` | Cabinet Office tsunami topography 2025 (10/30/90 m) | see its README | yes | `topobathy.io.grids.read_cao_2025`, comparison figures | not merged into any DEM (by decision) |
| `mesh500/` | JCG 500 m mesh depths (text tiles) | — | no | `read_mesh500`, comparison figures | reference only |
| `SRTM15plus/`, `GEBCO/`, `CUDEM/` | global / US coarse grids | — | no | `read_srtm15plus`, comparison | reference only |

## Present but not documented or not used by this repository

| directory | observation | what is needed |
|---|---|---|
| `tokyo_bay/dem_*_*.nc`, `depth_*.nc` (22 files, 2021) | GDAL-made grids of the Tokyo Bay mesh area (1982 × 2466 and 1622 × 1128); `dem_*` created from a personal GitHub path of a former collaborator; `depth_0030/0090/0270/0810-*` are the older Cabinet Office grids (30–810 m) | origin, datum and licence not recorded; only `depth_0030-*` is used (a comparison figure) |
| `tokyo_bay/SRTM15_*.nc`, `kanto_M7001*_srtm_15s.nc`, `.om_dem_cache/` | SRTM15+ extracts and M7001+SRTM blends (July 2026), cache of an earlier tool | not referenced by current code; candidates for tidy-up |
| `Akanehama_MLIT/` (8.6 GB, 2018–2020) | MLIT multibeam surveys, Chiba/Funabashi ports, sound-speed and tide files | no README, not referenced here; **a high-value source for Funabashi/Chiba** if the licence allows use |
| `sea_chart/TokyoBay/` | nautical chart (2016) | no README, not referenced |
| `osaka_bay/` | SRTM15 GeoTIFF of Osaka Bay | not Tokyo Bay; not referenced |

## Open items for the archive

1. Write READMEs for `tokyobay_endo/` and `tokyo_bay/` (top level), and `Akanehama_MLIT/`.
2. Record provenance and licence of `tokyo_bay/dem_*`, `depth_*`; decide keep / move / delete.
3. Ask Chiba Prefecture whether the Sanbanze "世界測地系" is JGD2000 or JGD2011.
4. Ask JHA / JCG for the survey years behind the M7001 contours near Tokyo Bay (earthquake question).
5. Decide whether the Akanehama MLIT multibeam data should enter the Futtsu/Chiba DEMs.

Deletion candidates are listed to the owner, never deleted here (see the repository rules).
