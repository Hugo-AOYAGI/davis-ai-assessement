# d20_n_housing source review

Reviewed on 2026-10-17 by Claude (Sonnet) directly against the supplied corpus and the
original PDF, before any experiment. No agent output was used as expected data. One manual
source review only; the planned two independent Opus drafts and disagreement review were
not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices; printed numbers are one lower.

Site: `evals/datasets/zoning/z07_natural_zone.yaml` (parcel 91272000CC0193, 16 Impasse de la
Gourdillerie). The GPU zone record reads `LIBELLE` = `N` with no sub-sector, so the plain
zone N of the Vallée chapter applies (a second N chapter exists for Chevry, PDF p.285).
The brief's `legend_items: []` was replaced by the one overlay the zoning item records as
present (emplacement réservé, partial coverage); the regulation text says nothing specific
about it for zone N beyond the N9.1 reference to graphic indications and the N6/N7
reconstruction clauses, so no statement is built on it.

Reviewed pages (rendered at 1.6x with PyMuPDF and viewed): 193 (intro, N1), 194 (N2),
197 (N6, N7.1), 198 (N7.2.2, N8), 199 (N9, N10); 195 and 200 were read as text only
(page200.png was rendered but not needed). Rendered images: [p193](page193.png),
[p194](page194.png), [p197](page197.png), [p198](page198.png), [p199](page199.png),
[p200](page200.png). No strike-through, table or graphic was found on the viewed pages;
the text layer is reliable.

- p.193 N1: new constructions for housing (and hotels, offices, craft, retail, industry,
  warehouse) are prohibited "autres que ceux admis en N2".
- p.194 N2: for the whole zone N, the only housing item is the extension of existing dwellings
  up to 15% of floor area. The 20% extension and new public facilities are Nc only; NL has
  outdoor sports works; Nca (p.195) has new activity buildings and housing arrangement tied
  to activities in existing buildings. Zone-wide N2 contains no new dwelling.
- p.197-199: setback 12 m from road axis (N6), 16 m from boundaries (N7, 8 m only Nca),
  N8 not regulated in N, N9 15% only in Nc/Nca/NL, N10 not regulated in N (10 m ridge in
  Nc/Nca/NL). These are secondary, non-critical statements.
- Observation (not a flag): the chapter intro (p.193) lists three sectors (NL, Nc, Nca)
  while N9 says "Dans les autres secteurs : Sans objet"; the site is plain N, so this does
  not affect the item.

## Review

An independent review found no fact covering the legend item. Two non-critical facts were
added from Titre III. p.366: construction is prohibited on land inside an emplacement
réservé. p.367 (list "pour équipements ou espaces publics"): entry Z, aire de retournement,
commune, Impasse de la Gourdillerie, 490 m², parcels CC 112, 136, 154. The entry is matched
to the site by street name and by the turning-area reservation recorded in
`evals/fixtures/zoning/SOURCE_NOTES.md` (z07). Limitation: the site parcel CC0193 is not
among the listed parcel numbers (likely a later cadastral division), and the reservation
covers only about 58% of it, so the match rests on the street and the purpose, not on the
parcel list. The legend label of the zoning item also mentions voirie, but the matching
entry is in the public-equipment list; no entry was found under the voirie list for this
street. Neither fact is critical.

Validation commands:

```text
uv run python -m evals.gt.check evals/datasets/doc/d20_n_housing.yaml
uv run python -m evals.gt.pages verify evals/datasets/doc/d20_n_housing.yaml
```
