# e05_vallee_ua_housing evidence note

Reviewed on 2026-10-17 before any end-to-end experiment. Expectations come from the
component items, the cadastre and the documents, never from agent output. Review method:
Claude Sonnet source inspection; the planned two independent Opus drafts and human sign-off
were not performed for this smoke set.

## Sources

- Site: no surveyor item exists. `z11_vallee_ua` (zoning) names parcel 91272000CA0005; the
  BAN row `91272_1260_00192` ("192 Avenue du Génèral Leclerc", sector Vallée) links it
  (`uv run python -m evals.gt.site ban "192 Avenue du Général Leclerc"`). The parcel
  neighbours are CA0004 (275 m2) and CA0006 (48 m2).
- Zone and overlays: `z11_vallee_ua` and its oracle `evals/fixtures/zoning/z11_vallee_ua.oracle.json`
  (archived 2021 GPU layers): 100% zone UA (no sector suffix), no surface prescription
  intersects, the nearest linear prescriptions are two road-widening reservations 4.5 m away
  (not on the parcel).
- OAP: `d09_outside_oap` and the same oracle: all 10 OAP perimeters have 0 m2 intersection,
  the nearest about 958 m away. Hence `oap_applicable: false`.
- Rules: `d01_ua_vallee_vs_chevry` for Vallée - UA (regulation PDF p.13-30), re-read directly
  on pp.13, 14, 18-23, 27-30. Chevry - UA (pp.210-221) is only the trap behind `must_not`.
- All page numbers are 1-based PDF indices. The 13 quotes in the YAML were checked with
  `evals.gt.pages verify` (13/13 at 1.00).

## Values retained (Vallée UA, plain UA, no sector)

| Rule | Value | PDF page |
| --- | --- | --- |
| Use | housing is the zone's main use; not in UA1 prohibitions | 13, 14 |
| Road (UA6) | at the current or projected alignment | 18 |
| Side/rear (UA7) | on boundaries within the 30 m band; setback 8 m with views, H/2 min 2 m without | 20 |
| Footprint (UA9) | 60% of the site, annexes included | 22 |
| Height (UA10) | 9 m eaves/acroterion, 12 m ridge, R+2+combles | 23 |
| Parking (UA12) | 2 per dwelling; 40% covered or underground | 27, 28 |
| Green (UA13) | no numeric minimum, only "plantées ou ... aménagement végétal ou minéral" | 29 |

Brief against sources: the brief's "9 m / 12 m; alignment; H/2 setbacks; 60 %" is confirmed.
Added from the sources: the 8 m setback with views, which is the non-trivial case (side
limits meeting the road and the rear limit share the same distances), and the absence of any
green-area ratio in UA13 (contrast e01, where UMG imposes 20%).

## Computations

- Site area: saved cadastral polygon (`z11_vallee_ua.cadastre.json`) projected to
  Lambert-93: 95.54 m2 (also 95.54 in the oracle; `evals.gt.site` prints 95.6 with its own
  rounding). The cadastre `contenance` field is 100 m2 and is not the geometry the agent
  measures; the 2% tolerance covers 95.5-95.6 but deliberately not 100 m2.
- Minimum green area: none (`min_green_area_m2: null`), as UA13 has no ratio.
- Footprint ground cap: 0.60 x 95.54 = 57.3 m2. No key exists for this cap in the output, so
  it is not a fact; the harness recomputes it from the submitted rules.
- Plot shape (minimum rotated rectangle): about 13.5 m x 8.4 m, shallower than the 30 m
  band, so the band wording is moot for this site.

## Choices and limits

- Heights: the contract holds one `max_height_m`, yet UA10 gives two cumulative limits
  (9 m eaves or acroterion, 12 m ridge). The source leaves open which one a prism volume
  uses, so the fact accepts 9 or 12 (critical) and the item has a `must_flag` for the choice.
  Storeys R+2+combles is accepted as 3 or 4 depending on whether the attic counts.
- Admissibility accepts permitted or conditional (UA2 has conditions only for other uses and
  flood zones).
- Side-band wording (p.20 "Dans une bande à compter de 30 mètres") literally reads "from
  30 m"; the next sentence restricts beyond 30 m to annexes, so it is read as "within 30 m".
  Not asserted, since it does not matter on a 8.4 m-deep-or-so plot.
- The `must_flag` on the ABF opinion is a gap pointing outside the corpus (monument
  perimeters are not in the documents).
- Limits of the site: at 95 m2, 8 m view setbacks leave little room, so a feasible building
  rests on blind facades or boundary walls; this is deliberate stress but unscored.
- No proposal volume is asserted: heights, facing windows and cut are the architect's
  choices. This item is not a complete oracle of every envelope rule (UA8 spacing is not
  scored: one building) nor of the achievable volume.
- Plan raster not re-read here: overlay absence rests on the GPU vector intersection reviewed
  in z11, itself an agent source review, not human sign-off.
