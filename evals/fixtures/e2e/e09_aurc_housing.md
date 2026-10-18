# e09_aurc_housing evidence note

Reviewed on 2026-10-17 by Claude Sonnet (`claude_sonnet_source_review`) directly against the
corpus PDFs, the saved cadastral feature and the archived 2021 GPU layers. No agent output was
used. One manual source review only; the planned two independent Opus drafts and human sign-off
were not performed. All page numbers are 1-based PDF indices (printed number = index - 1).

## Sources

- Parcel: BAN point of 59bis Route de Damiette (2.11381, 48.69822) lies inside cadastre parcel
  91272000BD0231 (`evals.gt.site near`; the BAN row has no cadastre link, so the parcel is chosen
  by point-in-polygon, as in `z15_aurc`). The neighbouring parcels (BD0021, BD0225, BD0263) are
  13-20 m away. There is no surveyor item for this site; `z15_aurc` supplies the parcel id and
  `evals/fixtures/zoning/z15_aurc.cadastre.json` the geometry.
- Zone and OAP: `z15_aurc` and its oracle (`evals/fixtures/zoning/z15_aurc.oracle.json`): the
  whole parcel (3405.97 m2) is in AURc (ZONE_URBA record 71, 34363 m2) and in the OAP surface
  (PRESCRIPTION_SURF, 34656 m2); recomputed here from `data/gpu_2021`.
- AURc chapter, regulation PDF pp184-191: p184 intro ("Elle couvre le secteur de Damiette et est
  complete par des orientations d'amenagement et de programmation") and AURc1 (any construction
  not respecting the OAP of sector Damiette is prohibited); p185 AURc2 (housing admitted subject
  to the OAP; 9000 m2 minimum site, waived for residual plots; coherent development of the zone);
  p185-186 AURc3, AURc4 defer to UR; p186-187 AURc6 own road setback (5 m if the right-of-way is
  8 m or more, 6 m otherwise); p188 AURc7, AURc8 defer to UR, AURc9 own footprint 20 %;
  p189 AURc10, AURc11 defer to UR, AURc12 own parking (2 per dwelling, one covered; 1 visitor
  space per 3 dwellings in operations d'ensemble); p191 AURc13 own green space (75 % of the site
  planted, one tall tree per 100 m2, 10 % common green space only above one hectare).
- UR chapter, pp154-160, read for the referred articles: UR7 p156 (setback 4 m minimum; 8 m with
  windows, 4 m without), UR8 p157 (16 / 12 / 8 m between buildings), UR10 p159 (7 m eaves or
  acrotere, 10 m ridge; no storey limit). The p159 and p188 renders show no strike-through
  (see `evals/fixtures/doc/d03_aurc_defers_to_ur/`).
- OAP PDF p14 (printed 13), chapter 4 "Le secteur Damiette (AURc)": about 15 dwellings, views to
  the Vallee preserved, transition with neighbouring districts, internal access from route de
  Damiette, soft circulations, green strip to be kept unbuilt (diagram). Qualitative only.

## Findings that differ from the brief

- The brief says "articles 10-11 defer to UR", as the d03 trap does; true, but AURc also defers
  for articles 3, 4, 7, 8 and sets its own 6, 9, 12 and 13. The item therefore expects the AURc
  footprint (20 %), road setback (alignment 5 / 6 m) and green space (75 %), not the UR values
  (10 % footprint, 10 m / 14 m road, no green minimum).
- The OAP chapter is 4 (Damiette), PDF p14, as `evals/README.md` says; the OAP also exists as
  chapters 5 (Rougemonts) and 8 (Joliot Curie), which must not be used.

## Computations

- Site area: cadastre polygon 3405.97 m2 (z15 oracle, Lambert-93) or 3406.2 m2 (`gt.site`);
  cadastre contenance 3413 m2. Expected 3406 m2 with 2 % tolerance covers all three.
- Minimum green area: 3406 * 0.75 = 2554.5 m2 (tolerance 2 %).
- Maximum footprint: 0.20 * 3406 = 681.2 m2 (not scored: no contract field holds a capped
  footprint; the ratio itself is a critical fact). AURc9 says "20 % de la superficie totale du
  terrain dans la zone"; read here as the site (terrain), the other reading (zone total, 34363 m2)
  would not be a per-parcel limit. No must_flag was set on this wording.

## Critical facts and their backing

- Parcel BD0231: cadastre point-in-polygon plus z15.
- Zone AURc and OAP applicable: z15 (archived 2021 GPU intersections).
- Admissibility permitted or conditional: p185 lists housing among admitted uses, subject to
  AURc2 conditions and the OAP; both verdicts accepted.
- Footprint 0.20: p188 quote checked.
- Height any_of 7 or 10: UR10.2 p159 via AURc10 p189, quotes checked; two figures by roof form
  (as in e05 for UA), hence `any_of`. Storeys: UR10 sets none, expected null (non-critical).

## Omitted oracles and limits

- No proposal volume or buildable-footprint area is asserted: the layout (cut, heights, windows,
  setbacks from the real plot edges) is the architect's choice; the harness recomputes it.
- Setback distance keys are limited to side rules (8 m / 4 m); the road distance (5 or 6 m) is
  covered by `must_flag` and `must_not`, because the contract may place it under either window
  case and the right-of-way width is not in the corpus. Spacing between buildings is not scored
  (one building program).
- Title I parking provisions were not reviewed; only the AURc12 housing ratio is scored.
- The 9000 m2 minimum (p185) is a real open point for a 3406 m2 parcel: whether BD0231 is a
  residual plot is not decided by the documents (`must_flag`, `must_not`).
- The OAP diagram position of the parcel relative to the green strip and view corridor was not
  measured.

## Validation

```text
uv run python -m evals.gt.check evals/datasets/e2e/e09_aurc_housing.yaml
OK e09_aurc_housing [e2e, verified] facts=16 must_flag=4 must_not=8

uv run python -m evals.gt.pages verify evals/datasets/e2e/e09_aurc_housing.yaml
10/10 quotes verified
```
