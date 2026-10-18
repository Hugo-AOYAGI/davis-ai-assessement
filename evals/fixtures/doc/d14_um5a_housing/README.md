# d14_um5a_housing source review

Reviewed on 2026-10-17 by Claude Sonnet directly against the supplied corpus and original PDF,
before any experiment. No agent output was used as expected data. This item had one manual source
review; the planned two independent Opus drafts and disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices (printed number = index - 1). Site: `z17_um5a`
(parcel 91272000CP0128, zone UM5a, legend item OAP sector applies).

Reviewed pages: 306-319 (zone UM chapter). Used: 310-311 (articles 6-7), 312 (articles 8-9),
313 (article 10), 315 (article 12), 318 (article 13).

Findings
- The case brief's trap ("UM5 rule applied where UM5a has its own") is only true for hotel
  accommodation. For housing UM5a has no rule of its own: p.313 gives housing 20 m, R+5 in UM5, and
  UM5a appears only as a sub-bullet of "autre destination" (31 m for hébergement hôtelier). Likewise
  p.315 gives UM5a its own parking ratio (1 per 2.5 rooms) only for hébergement hôtelier. Housing
  parking is the zone-wide rule (1 per 35 m² of floor area, max 2 per dwelling). The wrong readings
  recorded in `must_not` are therefore applying 31 m / 24 m / 25 m or the 2.5-room ratio to housing.
- Footprint: article 9 states it is not regulated (p.312).
- The input names the OAP legend item (from the zoning item); the regulation only requires
  compatibility with the OAP in document 3 (repeated in every article). OAP content is read by
  the `oap` task and is not evaluated here.
- No `must_flag`: no gap or ambiguity found in the UM chapter for housing. That UM5a inherits the
  UM5 housing rule is read from its placement inside the UM5 block (the UM intro lists only UM3,
  UM4 and UM5 as sectors).

Visual check: pages 311, 312, 313, 315, 318 rendered and inspected (`page311.png`, `page312.png`,
`page313.png`, `page315.png`, `page318.png`). No strike-through or table lost in the text layer.

Render command (PyMuPDF):

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[312].get_pixmap(matrix=pymupdf.Matrix(2,2)).save('evals/fixtures/doc/d14_um5a_housing/page313.png')"
```

Validation: `evals.gt.check` OK (verified, 15 facts, 4 must_not); `evals.gt.pages verify` 17/17
quotes verified.
