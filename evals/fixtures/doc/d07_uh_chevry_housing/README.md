# d07_uh_chevry_housing source review

Reviewed on 2026-10-17 by a Claude Sonnet worker directly against the supplied corpus and
original PDF, before any experiment. No agent output was used as expected data. This is a
single manual source review; the planned two independent Opus drafts and disagreement
review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
All page numbers are 1-based PDF indices (printed page = index - 1).

Reviewed pages: 256-268 (Chevry, zone UH, articles UH1-UH16); 99, 107-113, 116 (Vallée UH,
read only to build the `must_not` list).

- Zone UH of Chevry (p.256) is the isolated-house tissue, with two sectors UHa and UHb that
  differ in heights and architectural rules. The brief gives no sector, so the item states both
  where they differ (eaves height, levels) and the common value (ridge 10 m).
- p.261, UH6.3: road setback 4 m from the current or planned alignment (no axis-based rule).
- p.261-262, UH7.2: 2 m from side boundaries without windows, 4 m with ground-floor windows,
  windows on upper floors only at 6 m or more. UH7.1 defines the boundaries as "latérales et
  de fond de terrain", so the rear setback is the same rule (there is no separate rear rule).
- p.262, UH8.1: 8 m between buildings on one plot if a facade has windows, 4 m otherwise.
- p.263, UH9.2: footprint at most 1/3 of the site area. UH10.2 table (rendered below): ridge
  10 m in UHa and UHb, eaves 3 m (UHa) and 5.50 m (UHb), levels R+Combles (UHa) and
  R+1+Combles (UHb). See [page263.png](page263.png). No strike-through or other formatting
  changes the meaning of the table (checked on the render and on the page's vector drawings).
- p.266, UH12.1: 2 places per dwelling; 3 per dwelling plus 1 visitor space per 3 dwellings in
  new housing developments; extension rule not retained. UH12.2: at least 50% covered. See
  [page266.png](page266.png).
- p.267, UH13.3: one high-stem tree per 150 m² of free land, minimum 2 per site.
- p.257, UH2: housing admitted if it fits the architectural and landscape harmony.

Trap (Vallée UH, p.107-113 for comparison, not part of the expected answer): footprint 20%
of the site, road setback 5 m (or 9 m from the axis of a road under 8 m wide), side setback
8 m with windows or H/2 with a 2 m minimum, eaves 7 m and ridge 10 m. The item's
`must_not` list reflects those values. The Vallée UH chapter is p.99-120; Chevry UH is
p.256-268.

No `must_flag`: the zone chapter is complete for the focus topics and no corpus gap or
contradiction was found. Whether the site is in UHa or UHb is an input question settled by
the zoning plan, not a document ambiguity.

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d07_uh_chevry_housing.yaml
OK d07_uh_chevry_housing [doc, verified] facts=15 must_flag=0 must_not=7

uv run python -m evals.gt.pages verify evals/datasets/doc/d07_uh_chevry_housing.yaml
16/16 quotes verified
```

Quote matching verifies the literal text only. Table values (p.263) were read from both the
text layer and the rendered image.

## Review

An independent review raised two points, both fixed:

1. The parking statement gave only the general rule (2 spaces per dwelling), but p.266 also
   sets 3 spaces per dwelling plus 1 visitor space per 3 dwellings for "opérations d'ensemble
   nouvelles", and the program does not say which applies. The critical statement now states
   both cases with both quotes (the separate developments statement was merged into it), so it
   is unambiguous. A `must_not` now rejects answers giving only one of the two rules.
2. The `must_not` "ridge 11 m (Vallée UH)" was wrong: 11 m is the UHf figure (p.113). Vallée UH
   ridge is 10 m, the same as Chevry, so it did not discriminate. It was removed; the eaves
   7 m entry (Vallée UH, p.113) stays. The trap paragraph above lists the discriminating values.
