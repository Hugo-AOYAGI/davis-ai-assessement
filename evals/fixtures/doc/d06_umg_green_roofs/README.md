# d06_umg_green_roofs source review

Reviewed on 2026-10-17 by a Claude Sonnet source review directly against the
supplied corpus and the original PDF, before any experiment. No agent output
was used as expected data. One manual source review only; the planned two
independent Opus drafts and disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices (printed number = index - 1).

Reviewed pages: 318 (zone UM, same wording, not used), 330, 331 (UMG article 13),
376 (lexique, espaces végétalisés).

- Page 330 (printed 329), UMG 13.1: espaces verts need at least 60 cm of
  terre végétale; "les toitures végétalisées ne sont pas comptabilisées en espaces
  verts"; pleine terre excludes any infrastructure or superstructure.
- Page 331, UMG 13.3: new construction must treat at least 20% of the plot as
  espace vert and 10% as pleine terre. The quantitative rules do not apply to
  public-service or collective-interest facilities (not the offices program).
- Page 376 (printed 375), lexique "Espaces végétalisés (application des
  articles 13)": coefficient 1 for planted full-ground space and unsealed play
  areas; coefficient 0.5 for vegetated spaces on a slab or roof with at least
  30 cm of earth and for permeable parking; at least 50% of the required
  vegetated space must be full ground.
- Conflict: UMG 13.1 excludes vegetated roofs from green space (and a roof can
  never be pleine terre), while the lexique gives roof planting a 0.5 weight.
  The lexique heading says it applies to "les articles 13", but UMG article 13
  speaks of "espace vert" and "pleine terre" and never of "espaces végétalisés",
  and the regulation does not say which text prevails. This is recorded as
  `must_flag`. Case brief (green roofs 0.5 in the lexique vs not counted in
  UMG 13) matches the documents.
- Visual check: rendered pages 330 and 376 inspected; no strike-through,
  table or graphic changes the text-layer reading. Images:
  [page330.png](page330.png), [page376.png](page376.png).

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[329].get_pixmap(matrix=pymupdf.Matrix(2,2)).save('evals/fixtures/doc/d06_umg_green_roofs/page330.png')"
```

## Review

An independent review noted that a model can defensibly argue UMG 13.1 (specific,
p.330) prevails over the general lexique entry (p.376), since UMG 13 speaks of
"espace vert" / "pleine terre" rather than "espaces végétalisés". The `must_flag`
now requires only that both rules and the tension between them are reported,
whichever is said to prevail, and the third `must_not` now forbids only applying
the 0.5 roof coefficient to the UMG green-space minimum without noting the 13.1
exclusion.
