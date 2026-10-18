# d18_uhe_housing source review

Reviewed on 2026-10-17 by a Claude Sonnet source review directly against the supplied corpus
and original PDF, before any experiment. No agent output was used as expected data. One review
pass only; the planned two independent Opus drafts and disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices (printed number = index - 1).

Reviewed pages: 99-102 (zone intro, UH1, UH2, prescription perimeter), 107 (UH6), 109-111
(UH7, UH8), 112 (UH9), 113-114 (UH10), 116-118 (UH12), 119 (UH13).

Finding (differs from the case brief): UHe has no figures of its own for footprint, height,
setbacks or parking. Article UH9 groups "UH et UHe et UHf" (20% main / 5% annexes); UH10 gives
7 m eaves or acroterion, 10 m ridge, R+1+combles "En UH hors secteur UHf"; UH12 gives 2 spaces
per dwelling, one covered, "en zone UH hors secteur UHf". What differs in UHe is the extra ban
on subsoil exploitation (p.100) and the radiological conditions (p.99, 101-102). The trap is
therefore applying the figures of another sector (UHc 25%, UHd 30%, UHf 11 m) or inventing
UHe-specific figures, not omitting UHe figures.

Visual check: pages 112, 113 and 116 rendered (PyMuPDF, 1.6x) and inspected: no strike-through
on any figure (see `page112.png`, `page113.png`, `page116.png`). The other pages were scanned
for line drawings crossing text (`page.get_drawings()`): only header and footer rules, article
title rules and an underlined heading (p.101) were found, so no strike-through is expected.

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[112].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('evals/fixtures/doc/d18_uhe_housing/page113.png')"
```

Legend item: the zoning item `z19_uhe` lists "Zone correspondant au périmètre de prescriptions
sanitaires" as the applying overlay; the regulation provisions for it are on p.101-102.

Validation: `evals.gt.check` OK (16 facts, 4 critical, 5 must_not); `evals.gt.pages verify`
26/26 quotes verified.

## Review

An independent review found three problems, fixed on 2026-10-17:
1. The parking statement gave only the p.116 rule (2 per dwelling, one covered). UH12.4 (p.118)
   requires 3 per dwelling plus 1 visitor space per 3 dwellings in new operations of more than
   3 dwellings (all zones except UHc), and the input gives no dwelling count. The critical
   statement now states both cases with both quotes; the separate p.118 statement was merged
   into it, so no fact contradicts it.
2. The `must_not` on UHf figures listed visitor parking, which a correct answer citing p.118
   would trip. "visitor parking" was removed from it.
3. Added a fact for UH7 (p.110): beyond the 25 m strip only terraces and annexes are allowed
   (page text checked, no strike-through).

Re-run: `evals.gt.check` and `evals.gt.pages verify` both pass.
