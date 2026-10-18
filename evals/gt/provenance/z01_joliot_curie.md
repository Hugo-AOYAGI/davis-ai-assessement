# z01_joliot_curie: independent verification

Verified on 2026-10-17 using local archived source files, without running the
agent under test. The input parcel is the hand-selected reference parcel from
`s01_joliot_curie`, not an upstream agent prediction.

## Reproduce

`uv run python -m evals.gt.zones.oracle` reads
`tests/adapters/geo/fixtures/cadastre_CR0247.json`, reprojects WGS84 coordinates
to Lambert-93 (EPSG:2154), intersects the complete parcel with the archived
`data/gpu_2021/91272_*_20210706` shapefiles and prints record numbers, areas,
distances and SHA-256 hashes. No network service or model is involved.

The archive is `91272_PLU_20210706`, already downloaded in this workspace from
the GPU archive (see `evals/README.md`). This verification does not claim
to have downloaded it again or to have independently recovered its original URL.
The local layers are ignored data, so another checkout needs the archive first.

## Geometry results

The saved cadastral fixture identifies `91272000CR0247`. Its measured area is
5951.492549 m². Its administrative `contenance` is 5960 m²; the area measurement
is used only to check geometric coverage here.

- ZONE_URBA record 36, LIBELLE `UMG`, IDURBA `91272_PLU_20210706`:
  intersection 5951.492549 m², effectively 100% of the parcel. No other zone intersects.
- PRESCRIPTION_SURF records 9 and 10, TYPEPSC `18`, TXT `OAP`: each intersects
  5951.492549 m². These are two nested generic OAP geometries. The item checks
  the printed generic OAP legend label, not an unverified name for either feature.
- No other surface prescription intersects the parcel. The nearest EBC is
  132.08 m away; nearest PPRi geometry 1574.75 m; nearest wetland 255.28 m.
- No linear prescription intersects the parcel. Linear absence is not scored.

OAP record 9 bounds (L93): (638277.049395, 6845573.793017,
639076.411084, 6846075.587520). Record 10 bounds: (637524.55,
6845314.87, 639123.87, 6846814.28). Generic GPU labels alone do not identify
their sector names; no name-specific assertion is scored.

## Raster cross-check

Inspected the actual raster plan, `ressources/plu_reglement_graphique_91272_20210706.pdf`,
PDF page 1. The northeastern Joliot-Curie area is labelled UMG with a pale pink
fill and a magenta dotted OAP perimeter. The nearby NF area south of the road
has the green EBC pattern; the UMG land north of that area does not. Legend
labels were transcribed visually from this page, including:

- `Secteur à Orientation d'Aménagement et de Programmation`
- `Espaces Boisés Classés`
- `Zone de risques d'inondation (PPRi Vallée de l'Yvette approuvé le 26 septembre 2006)`
- `Zone humide`

The three scored absences use full-parcel oracle intersections and positive
separation distances, cross-checked against the legend patterns. Other possible
legend absences are deliberately unscored. This is not a claim that the item
exhaustively verifies every graphic prescription.

## Source hashes

SHA-256 (the helper also prints DBF and projection hashes):

| Source | SHA-256 |
| --- | --- |
| cadastral fixture | `eac98d478b64ec0ed39d0571655a278bc94fd5ff66a694dfe869381129472b23` |
| ZONE_URBA SHP | `31ab43685e33cf2eb604cf1a7f2b9d30e7b0f9b369082dbbb5f7931b9af70890` |
| ZONE_URBA DBF | `aa6f1f501a3ee128bdd814e2963e956d66fc47425517f386e6d06e47c8dab28f` |
| PRESCRIPTION_SURF SHP | `0c9fea94e3dc9dd11aa1ed0983bbae72b8e8b058cfc342f1f1c8e9d7dc6f30a5` |
| PRESCRIPTION_SURF DBF | `b6693faa375dd41dcac004197241ecedd82181c2438da134b3d295e3bdb989d4` |
| PRESCRIPTION_LIN SHP | `d308f96f125cfc472fef7554b921021dd04cbebf1dc994d44543391d60c41379` |

## Scoring limit

`ZoneFindings` has no citation fields. The fact scorer can therefore score its
answers but cannot establish citation grounding. The YAML intentionally omits
`evidence`, otherwise correct answers would systematically fail: `resolve`
cannot find citations and `matcher.cited` returns false. Consequently, its
reported grounded score currently equals its answer score (`cited: null`).
Raster evidence is documented above; this is not a measurement of whether the
model inspected the correct parcel crop. A later harness change should score
the typed image region and its provenance explicitly.
