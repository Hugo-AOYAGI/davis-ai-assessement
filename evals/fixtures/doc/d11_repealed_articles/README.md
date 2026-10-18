# d11_repealed_articles source review

Reviewed on 2026-10-17 by a Claude Sonnet source review directly against the supplied
corpus and original PDF, before running any experiment. No agent output was used as
expected data. One reviewer only: the planned two independent Opus drafts and the
disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
All page numbers are 1-based PDF indices; printed numbers are one lower.

Site and chapter: parcel 91272000CO0051 (5 Chemin de Moulon, item `z03_ebc`) is zoned
UH with an Espaces Boisés Classés overlay. The Moulon plateau chapter has no UH zone, so
the parcel falls under the UH chapter of the Vallée sector (PDF p.99-120), not the
Chevry UH chapter (p.256-268). The zone is the plain UH (not UHc/UHd/UHe/UHf).

- Page 106, UH5: heading "Superficie minimale des terrains constructibles", body only
  "Abrogé par la loi ALUR du 24 mars 2014". Rendered: [page106.png](page106.png).
- Page 119, UH14: heading "Coefficient d'occupation du sol", body only "Abrogé par la
  loi ALUR du 24 mars 2014". Rendered: [page119.png](page119.png).
- Page 112, UH9: UH footprint 20% of the plot for main constructions (annexes 5%).
  Rendered: [page112.png](page112.png).
- Page 113, UH10.2: UH (outside UHf) 7 m at eaves or acroterion, 10 m at ridge,
  R+1+combles. Rendered: [page113.png](page113.png).
- Rendered pages show no struck-through values; the text layer and image agree.
- Residual mentions: Titre I (p.8) still says "coefficient d'occupation des sols
  applicable dans la zone" in the hamlet rule (zone UB), and bicycle rooms have a 3 m2
  minimum area; neither is a UH plot-size or COS rule, so no `must_flag` is set.

The brief's `trap` (stating a minimum plot size or a COS) is confirmed by the documents.

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[105].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('evals/fixtures/doc/d11_repealed_articles/page106.png')"
```

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d11_repealed_articles.yaml
uv run python -m evals.gt.pages verify evals/datasets/doc/d11_repealed_articles.yaml
```

Both pass (6/6 quotes verified).

## Review

Independent review by the coordinator: OK. Vallée UH confirmed (the plan crop shows the
UBa plan-masse sector next to the parcel, which exists only in the Vallée chapter).
Gap found: the context lists "Espaces Boisés Classés" but no fact covered it. Added one
non-critical fact from UH13.1 (PDF p.118, printed p.117): the classement forbids any
change of use or occupation that compromises the woodland. Facts are now 7.
