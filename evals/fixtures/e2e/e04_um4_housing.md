# e04_um4_housing oracle

Reviewed on 2026-10-17 by Claude Sonnet directly against the supplied corpus, the cadastre
and the component items. No agent output was used as expected data and no agent or experiment
was run. Review method: one manual source review; the planned two independent Opus drafts and
human sign-off were not performed.

Sources: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`, SHA-256
`e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`) and
`ressources/oap_91272_20210706.pdf` (corpus id `oap`). Page numbers are 1-based PDF indices
(the printed number in the regulation is one lower).

## Site and zone

- No surveyor item exists for this address. BAN row `91272_2077_00008` (8 Mail Pierre Potier,
  Moulon, found with `evals.gt.site ban "Mail Pierre Potier"`) carries `cad_parcelles`
  `91272000CP0123`. `evals.gt.site near` places the BAN point inside CP0123 (0.0 m); no
  neighbouring parcel touches it. `evals.gt.site parcel 91272000CP0123`: contenance 3429 m2,
  polygon area 3431.5 m2, frontage on unregistered ground (road) 237 m.
- Rue Pierre Potier and Mail Pierre Potier addresses link to other Moulon parcels (CP0220,
  CR0213); the second fact rejects them.
- Zone and OAP: `z16_um4` (archived 2021 GPU intersection, fraction 1.0 for UM4, legend item
  "Secteur à Orientation d'Aménagement et de Programmation"; provenance in
  `evals/fixtures/zoning/z16_um4.oracle.json`). OAP applicability is therefore true. The
  UM regulation (p306) says the zone is split into UM3, UM4 and UM5, "variations de la hauteur".

## Regulation (UM chapter, PDF pp306-319)

- p306: housing is an intended UM use; article 1 does not prohibit it (verdict permitted, or
  conditional because every article requires OAP compatibility, hence `any_of`).
- p313, article 10.2: UM4 housing 20 m with R+5 (6 storeys); other destinations in UM4 18 m;
  UM3 15 m; UM5 housing 20 m R+5, other 24 m, public/collective 25 m; UM5a hotel 31 m.
  Housing is 20 m / R+5 in UM4 and UM5 alike, and also in UMG (p326), so the height value alone
  does not separate the sub-sectors; the trap is the other values and the UMG chapter.
- p312, article 9: footprint not regulated (expected `null`).
- p318, article 13.3: 20 % green space, 10 % deep soil, trees per 300 m2; surface parking and
  vegetated roofs do not count as green space (13.1).
- Not scored (no matching contract field or layout dependent): deep soil 10 %, tree count,
  setbacks (road alignment or at least 1 m, p310-311; boundaries on limit or H/2 min 5 m, 6 m
  above 12 m, 3 m blind, p311; between buildings 10 m / 3 m, p312 - one building only),
  parking (p315, p317).

## Computations

- Site area: 3431.5 m2 (cadastre polygon, 2 % tolerance also covers contenance 3429).
- Minimum green area: 3431.467 x 0.20 = 686.29 m2, recorded as 686.3.

## Open points (must_flag)

- OAP PDF p25: for zone UM "le principe d'épannelage correspond à R+4 moyen" and the regulation
  heights are "normes plafond communes"; the PLU ceiling R+5 / 20 m is not a target.
- Parking: p315 housing 1 per 35 m2 of floor area capped at 2 per dwelling, 1 per dwelling
  for State-aided loans; Titre I (PDF pp5-6) caps State-aided rental housing at 1 per dwelling.
  The program states no financing.

## Quotes and limits

The five PLU quotes in the YAML were checked with `evals.gt.pages verify` (5/5 at 1.00) and the
OAP quote with `evals.gt.pages verify oap 25` (1.00). Page 313 was rendered (the d13 fixture
`page313.png`) and shows no struck-through text. `evals.gt.check` passes.

No proposal volume is asserted: one building still allows free choices of height (up to 20 m),
cut and windows, so the harness recomputes the proposal from the submitted layout. Site area,
green area and selected rule parameters are the only fixed envelope oracles. This is not a
complete oracle of every envelope rule.
