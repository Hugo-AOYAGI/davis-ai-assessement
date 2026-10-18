# Source audit: e08_uh_housing

Reviewed before launching any end-to-end experiment, on 2026-10-17. Expectations come
from source documents, the cadastre, the archived 2021 GPU export and the component
items, never from agent output. Review method: Claude Sonnet source inspection and
scripted geometry checks; the planned two independent Opus drafts and human sign-off
were not performed.

## Site choice

Candidates were the three UH zoning items. All three parcels are labelled plain `UH` in the
archived 2021 GPU zone layer (`data/gpu_2021/91272_ZONE_URBA_20210706.shp`).

| Item | Parcel | Overlay | Choice |
| --- | --- | --- | --- |
| z03_ebc | 91272000CO0051, 5 Chemin de Moulon, 3818.8 m2 | partial EBC (38.63 %); no PPRi, no wetland | chosen |
| z04_ppri | 91272000BK0007 | PPRi over the whole parcel | rejected (prefer no PPRi) |
| z05_emplacement_reserve | 91272000BE0321 | emplacement reservé (8 %) | not chosen |

z03 has no PPRi, and its partial EBC gives the "ignoring the site's overlay" trap.

## Sector evidence (Vallée UH, not Chevry UH)

The regulation has two UH chapters, found by scanning the page headers of the regulation PDF:
Vallée - UH (PDF pp99-120) and Chevry - UH (PDF pp256-268). There is no UH chapter for
Moulon (Moulon chapters: UM, UMG, UME, NE, NF, A, N).

1. Label logic. Chevry UH exists only as sectors: p256 "Elle comporte deux secteurs UHa et UHb"
   and the GPU has `UHa` (3 polygons) and `UHb` (3 polygons) for it. Vallée UH has the generic
   zone `UH` plus sectors UHc, UHd, UHe, UHf (p99). CO0051 is 100 % (3818.79 m2, fraction
   1.0000) inside a record labelled exactly `UH` (`z03_ebc.oracle.json`, record 117), so it is
   not in UHa/UHb and therefore not in the Chevry UH chapter.
2. Location. Parcel centroid in Lambert-93 is (637760, 6845145), on the Vallée side east of
   the Chevry plateau. Distances from the parcel to the nearest polygons by label: UHf 518 m,
   UMG 686 m, UA 1273 m, UHe 1359 m, UHd 1753 m, UHb 2112 m, UHa 2804 m. The nearest Chevry UH
   sector is more than 2.1 km away, and the Vallée UH sectors UHf (rue Gustave Vatonne) and
   UHe are the near ones. Chevry's UA parcel in z08 (AH0198) lies at x 634.5-635.2k.
3. Plan crop. `evals/fixtures/zoning/z03_ebc.review.png` shows the parcel inside a wide `UH`
   area with no sector suffix, bounded to the north by Nc/N (the EBC wood) and with the UBa
   sector further south; no Chevry UA/UE/UH labels. This is a visual cross-check only.

Conclusion: parcel 91272000CO0051 (z03) is in **Vallée UH**. It is not in Chevry UH. The
d11 item (Vallée UH, whose context names CO0051) is the matching doc item; d07
(Chevry UH) must not be used. The planned e08 row in `evals/README.md` (Chevry UH, 1/3 footprint,
4 m, 2/4/6 m) cannot be built on z03, z04 or z05: all three are plain Vallée UH. That
scenario needs a UHa/UHb parcel, which none of the three candidates is. The repealed-articles
trap of the brief (UH5 and UH14) matches the Vallée chapter (d11).

## Facts and sources

All page numbers are 1-based PDF indices; the 12 quotes in the YAML were checked with
`evals.gt.pages verify` (12/12 at 1.00) and `evals.gt.check` passes.

- Parcel and address: z03 BAN row `91272_1880_00005` with `cad_parcelles` = 91272000CO0051;
  cadastre polygon area 3818.79 m2 (contenance 3821 m2). Expected `site_area_m2` 3818.8, 2 %.
- Zone UH, EBC present, PPRi and wetland absent: z03 oracle (archived 2021 GPU). EBC covers
  1475.0 m2 (38.63 %); nearest PPRi 493.5 m, nearest wetland 366.8 m.
- OAP: no OAP surface intersects the parcel; the nearest OAP surface is 197 m away. Hence
  `oap_applicable: false` (not critical).
- Footprint (p112, UH9.2): 20 % of the site area for main constructions, 5 % for annexes.
  Derived maximum footprint 0.20 x 3818.79 = 763.8 m2. Not scored: no contract field holds it.
- Height (p113, UH10.2): 7 m at the eaves or acroterion, 10 m at the ridge, R+1+combles.
  Both heights are accepted for `max_height_m` (`any_of: [7, 10]`), and 2 or 3 for
  `max_storeys`; the choice depends on the roof form.
- Side and rear setbacks (pp109-110, UH7.2): 8 m with windows; H/2 with a 2 m minimum without.
  UH7.1.1 covers the side and the rear limits alike. H is measured to the eaves or acroterion.
- Road setback (pp107-108, UH6.3-6.4): 9 m from the axis if the road right-of-way is under 8 m,
  5 m from the alignment otherwise, with an easing along chemins and sentes. Not scored
  as a fact because the right-of-way width of the Chemin de Moulon is not in the corpus; it
  is a `must_flag`.
- 25 m band (pp109-110, UH7.1.2, 7.2.1): main buildings only within 25 m of the serving roads;
  beyond, terraces and annexes only. Also a `must_flag`: the envelope rules have no field for it.
- Green (p119, UH13.3): vegetated spaces at least 70 % of the site (UH, UHe, UHf); the lexique
  (p376) weights them (1 for open ground, 0.5 on slab) and requires half in open ground.
  Minimum green area 0.70 x 3818.79 = 2673.2 m2.
- Parking (p116, UH12.2): 2 spaces per dwelling, one covered.
- Repealed articles: UH5 (p106) and UH14 (p119), from d11; hence the two `must_not`s.
- Overlay: UH13.1 (p118) protects EBC from any occupation compromising the woodland.

## Limits

- No single proposal volume is asserted: footprint cut, heights and windows are the
  architect's choices and the harness recomputes the proposal. The item is not a complete oracle
  of every envelope rule.
- The road setback, the 25 m band and the position of the buildable part relative to the EBC
  depend on the road width and on a cadastral layout that was not read by a human on site.
- The unscored OAP result rests on GPU surface geometry, not on a visual check of the plan.
- `admissibility.verdict` accepts permitted or conditional: housing appears in neither the UH1
  prohibitions nor the UH2 conditions, but p101 lets any construction be refused or conditioned
  for safety or health.
