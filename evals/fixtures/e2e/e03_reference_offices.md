# Reference study oracle: offices on the Joliot Curie site

Reviewed on 2026-10-17, before any end-to-end experiment. Expectations come from source
documents and component ground truth, never from output being evaluated. Review method: one
Claude Sonnet source inspection (text layer read with `evals.gt.pages`, quotes machine-checked);
the planned two independent Opus drafts and human sign-off were not performed.

Sources: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`, SHA-256
`e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`) and
`ressources/oap_91272_20210706.pdf`. All pages are 1-based PDF indices (printed number minus 1).

## Component facts reused

- Parcel: `s01_joliot_curie` chooses CR0247 and rejects the CR0249 strip. Cadastre polygon
  area 5951.5 m2 (`evals.gt.site parcel 91272000CR0247`), `contenance` 5960 m2; the expected
  5951.6 m2 carries the 2% tolerance used by e01.
- Zone and OAP: `z01_joliot_curie` (archived 2021 GPU): 100% UMG, OAP perimeter present
  (`evals/gt/provenance/z01_joliot_curie.md`).
- Green roofs: `d06_umg_green_roofs` (pp330, 331, 376).
- Heights, footprint, art. 13 exemption wording: `d05_umg_public_interest` (pp326, 331).

## Pages read for this program

- p320, UMG art. 1: prohibited uses are agriculture/forestry, warehouses (entrepôt), caravans,
  camping and similar; offices are not listed, and the zone intro names "activités économiques"
  among the intended uses. The verdict is `permitted`, with `conditional` also accepted because
  every article requires compatibility with the OAP. p321, art. 2 holds no office condition.
- p326, art. 10.2: 25 m public service or collective interest; 20 m and R+5 for main
  destination housing; "autre destination" 18 m. Offices are neither of the first two, so 18 m
  and no storey limit (a storey limit is expected `null`; R+5 is a housing-only limit).
  Art. 9: footprint "n'est pas réglementée".
- p325, art. 7: side and rear boundaries (art. 7 covers "limites latérales et de fond"): build on
  the boundary or set back 6 m with windows (vues), 3 m without. Art. 8 spacing (10 m / 6 m)
  is not asserted: a single office building has no facing facade on the plot, so the agent may
  legitimately leave it null. Art. 6 (road: alignment or at least 1 m, p324) is not scored
  because the contract encodes it ambiguously (`on_limit_allowed` plus a distance).
- p327, art. 12.1: offices need 1 car space per 50 m2 of floor area (surface de plancher).
  Housing norms on the same page (1 per 35 m2 within 2 per dwelling; 1 per dwelling;
  1 per 150 m2 student residences) are the trap. p329 art. 12.5: office car spaces built on
  the plot must be 100% integrated in the construction; art. 12.3 bicycles: 1.5% of created
  floor area. Neither has a field in the study contract and neither is scored.
  p5-6, Titre I art. 2.2 caps required spaces at one per dwelling for State-aided rental
  housing, elderly-care facilities and résidences universitaires only; it does not touch offices.
- p330-331, art. 13: 20% green space and 10% full-ground space for new construction (the
  quantitative rules are lifted only for public services and collective-interest facilities,
  not offices). Art. 13.1: green space needs 60 cm of earth; vegetated roofs and surface
  parking do not count. p376 lexique: roof planting with at least 30 cm of earth weighted 0.5
  (see d06): the conflict is the `must_flag`.
- OAP pp33-36: no office-specific provision; the R+4 average objective concerns main-destination
  housing (d08) and must not be applied to offices.

Quotes in the YAML (11) were checked with `evals.gt.pages verify`: all matched at 1.00.
`evals.gt.check` passes. Every fact key was also checked against the `VerifiedStudy` field tree
(list selectors on `kind`, `basis` fields exist). Parking facts select by
`basis=floor_area_m2` rather than the agent's free-text use label, and building facts read all
buildings without a label selector, so they do not depend on how the agent names the building.

## Computations

- Minimum green area: 5951.6 x 0.20 = 1190.32 m2 (tolerance 2%). Full-ground minimum
  (10% = 595.16 m2) is not scored, the envelope contract has no field for it.

## Limits

- No fixed proposal volume is asserted: cut, shares, heights (any value up to 18 m) and facing
  windows are free layout choices. The harness recomputes the submitted proposal; this item
  scores only site area, minimum green area and the cited rule parameters. It is not a complete
  oracle for all envelope rules.
- Titre I p5 also refers to code provisions on parking within 500 m of stations or dedicated
  transit stops "lorsque les conditions de desserte le permettent". Whether the site lies in
  such a perimeter is not settled by the corpus, so no fact or `must_flag` depends on it.
- Floor area is not supplied in the input, so the parking requirement is scored as a ratio,
  not a number of spaces.
- The 2% tolerance on site area covers the gap between the polygon area and the cadastral
  `contenance` (5951.5 vs 5960 m2, 0.14%).
