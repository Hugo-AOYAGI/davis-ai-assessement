# e06_chevry_ua_housing evidence note

Reviewed on 2026-10-17 by a Claude Sonnet source-review pass directly against the corpus, the
cadastre and the component items, before any experiment. No agent output was used as expected
data. One review only: the planned two independent Opus drafts and human sign-off were not done.

Source regulation: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`),
OAP: `ressources/oap_91272_20210706.pdf` (id `oap`). All pages are 1-based PDF indices.

## Components reused

- `z08_chevry` (verified): parcel 91272000AH0198 is 100 % UA of Chevry, not Vallée; the OAP
  surface (generic GPU label, type 18) covers it fully; no EBC, PPRi or wetland
  (`evals/fixtures/zoning/z08_chevry.oracle.json`).
- `d12_ua_chevry_housing` (verified): the Chevry UA chapter (PDF pp210-221) values for
  footprint, height, setbacks, spacing, parking. Quotes re-verified here (11/11 at >= 0.99).
- There is no surveyor item. The BAN export lists 9 Allée du Pré Chevalier with
  `cad=91272000AH0198` (`evals.gt.site ban "Pré Chevalier"`: all 8 rows of that street point to
  AH0198), and `evals.gt.site parcel 91272000AH0198` confirms it exists (contenance 3711 m2).

## Facts and sources

- Zone UA, admissibility: p211 UA2 admits housing "sous condition de s'intégrer dans
  l'harmonie architecturale et paysagère"; `any_of [conditional, permitted]` because the
  condition is qualitative.
- Footprint (p217, UA9.2): 50 % of the site, main constructions (garages and parking under a
  landscaped slab excluded). Expected ratio 0.5.
- Height (p217, UA10.2): 12 m eaves, 15 m ridge, R+3 including converted attics (4 storeys).
  The envelope contract holds a single `max_height_m`, so either measure is accepted
  (`any_of [12, 15]`); the Vallée values (9 m / 12 m / R+2+combles) are in `must_not`.
- Road setback (p215, UA6.3): alignment or setback, no minimum. Side (p215, UA7.2): on the
  lateral boundary or set back by at least the eaves height, with no distinction by views.
  The side distance is deliberately not scored by key: with no views/no views split the agent
  may fill `with_windows`, `without_windows` or both. Only `on_limit_allowed` is scored; the
  Vallée side rule is in `must_not`. The rear limit is not scored (7.1 covers lateral and rear
  limits, 7.2 names only the lateral one; d12 did not flag it either).
- Spacing between buildings (p216, UA8.1): at least the eaves height of the taller one, min 4 m
  without views, 8 m with views. Scored by `min_m` although the program has one building.
- Green space (p220, UA13): only qualitative planting duties, no numeric share. Expected
  `min_green_ratio = null` and `min_green_area_m2 = null`. The 20 % green share in the corpus
  is UMG (p331), a trap. I read the whole chapter UA13 (p220) and searched the document for
  "pleine terre" and "biotope": no Chevry UA percentage.
- Parking (p219, UA12): 2 spaces per dwelling, at least 50 % of dwelling spaces in basement or
  ground floor. The Titre I cap (pp5-6: at most one space per dwelling) concerns aided rental
  housing, care homes for the elderly and university residences, so it does not apply to the
  ordinary private housing stated in the input (listed in `must_not`).
- Site area: cadastre polygon, 3681.2 m2 (L93 reprojection in the z08 oracle) to 3681.5 m2
  (`evals.gt.site parcel`), against a declared contenance of 3711 m2 (+0.8 %). Expected 3681.4
  with 2 % tolerance, which covers all three figures.
- Derived figure, not scored by key: maximum footprint under UA9 = 0.5 x 3681.4 = 1840.7 m2.
  The achievable ground area also depends on the eaves-height setbacks and on the free layout,
  so no `bounds` or proposal figure is asserted. The harness recomputes the envelope from the
  submitted rules; the omission of a volume oracle is intentional.
- OAP applicability (GPU 2021, whole parcel in an OAP surface): `true`, not critical, because
  the GPU labels every OAP surface generically; the Plateau de Chevry OAP (pp3-10) is the
  relevant document. It is qualitative: p8 asks to respect existing volumes and numbers of
  levels of collective-housing ensembles; p10 asks for renewal within existing footprints and
  volumes. This is the first `must_flag`.

## Open points (must_flag)

1. Qualitative OAP orientations (pp8-10) versus numeric UA limits.
2. Three simultaneous height limits (12 m eaves, 15 m ridge, R+3).
3. UA10.2 facade-on-road height cap tied to the road width, which the corpus does not give.

## Limits

- The parcel is an existing housing development (BAN lists numbers 4-25 of the street on
  AH0198); the item treats it as a free site by program fact. Existing buildings are not
  modelled.
- UA11 (p218) limits residential facades to 25 m in one vertical plane and p210 requires
  the Architecte des Bâtiments de France's opinion (registered site); both are conditions the
  study may list, not scored here.
- Not a complete oracle of every envelope rule or of the best achievable volume.

## Validation

```text
uv run python -m evals.gt.check evals/datasets/e2e/e06_chevry_ua_housing.yaml
uv run python -m evals.gt.pages verify evals/datasets/e2e/e06_chevry_ua_housing.yaml
```
