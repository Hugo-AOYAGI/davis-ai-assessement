# Reference public-facility study oracle

Reviewed on 2026-10-17 before any end-to-end experiment. Expectations come from the
component items, the cadastre and the regulation PDF, never from agent output. Review
method: one Claude Sonnet source review (the Sample worker). The planned two independent
Opus drafts and human sign-off were not performed; this is a source-checked smoke item,
not completion of the benchmark plan.

Pages are 1-based PDF indices of `plu_reglement` (corpus `ressources/plu_reglement_91272_20210706.pdf`)
and `oap`. The 7 explicit YAML quotes were checked with `evals.gt.pages verify` (7/7 at 1.00),
and the file loads with `evals.gt.check`.

## Sources by fact

- Parcel CR0247, CR0249 excluded: component `s01_joliot_curie` (same address and site as
  e01). Cadastre: `uv run python -m evals.gt.site parcel 91272000CR0247` gives contenance
  5960 m2 and polygon area 5951.5 m2; CR0249 is a 116 m2 strip.
- Zone UMG and OAP applicable: component `z01_joliot_curie` (archived-2021 GPU
  intersections, `evals/gt/provenance/z01_joliot_curie.md`).
- Height 25 m: regulation p326, UMG 10.2, first bullet, main destination "service public ou
  d'intérêt collectif". Component `d05_umg_public_interest` re-read; the rendered page was
  inspected there (no strike-through). The housing bullet (20 m, R+5) and the other-destination
  bullet (18 m) are the trap values. Sector UM4 (p313) gives 20 m to such facilities; it is a
  different zone.
- Storeys null: R+5 is stated only in the housing bullet; no storey limit is given for the
  public-service bullet (non-critical).
- Footprint null: p326, UMG 9, "n'est pas réglementée" (OAP compatibility required, no ratio).
- Green ratio null and minimum green area null: p331, UMG 13.3. The 20% green, 10% open
  ground and tree rules are followed by the sentence that the quantitative provisions "ne sont
  pas applicables aux constructions et installations nécessaires aux services publics ou
  d'intérêt collectif". The lexique (p375) defines CINASPIC as exactly these constructions and
  installations, and "Equipements collectifs" (p376) as public or private facilities serving
  residents (administrative, sport, culture, health, social, school). The harness maps
  `min_green_ratio = null` to `min_green_area_m2 = null`
  (`src/agent/runtime/geometry/envelope/study.py`), so the area is expected as null, not 0
  and not 5951.6 x 0.20 = 1190.32 m2 (that figure is e01's housing value and is the trap).
- Site area 5951.6 m2, tolerance 2%: cadastre polygon, as in e01.
- Setbacks (non-critical, same for every UMG use): p324 art. 6.3 road alignment or setback of
  at least 1 m; p325 art. 7.2.1 side/rear boundary 6 m with vues, 3 m without; building on a
  boundary allowed. Spacing between buildings (10 m / 6 m) is not scored: one building.

## Open points kept as must_flag

- Parking (p328, 12.1): a public service or collective-interest building has no ratio, only a
  case-by-case determination; higher education and research (1 space per 170 m2 of floor
  area) is the exception. The program does not name the facility, so the number cannot be
  fixed from the corpus.
- OAP (pp33-36): UMG articles 6-13 all require compatibility with OAP 8. Its only quantified
  height objective (p33, R+4 average) targets housing; nothing sets a facility height. The
  PLU 25 m limit is therefore the cited parameter and the OAP remains a compatibility check.

## Terminology

The brief says "équipement d'intérêt collectif"; the UMG text says "service public ou
d'intérêt collectif". They are treated as one destination, as in d05.

## Omitted oracles

No proposal volume, footprint or building height below the maximum is asserted: with one
building the cut, the height chosen (any value up to 25 m) and the setbacks used remain the
architect's choices, and the harness recomputes the proposal from the submitted layout. The
item does not score parking figures, appearance, access or networks, and is not a complete
oracle for every envelope rule.
