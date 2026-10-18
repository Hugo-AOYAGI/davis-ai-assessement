# d16_ugc_housing source review

Reviewed on 2026-10-17 by Claude Sonnet directly against the supplied corpus and original
PDF, before any experiment. No agent output was used as expected data. This item has one
manual source review; the planned two independent Opus drafts and disagreement review were
not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices (printed number = index - 1).

Reviewed pages and what they give for sector UGc (site of `z14_ugc`, no legend item applies):

- p.80: UGc is "le secteur UGc ... site proche de la gare de Courcelle".
- p.86 (UG6): UGc, UGe, UGf: "Les constructions seront implantées en retrait." No distance is
  given for UGc. The general UG sentence (alignment, or 9 m / 5 m by road width) is not
  expressly excluded for UGc: recorded as a `must_flag`.
- p.87-88 (UG7): the general rule (8 m with views; L=1/2H, min 2 m without) applies to UGc;
  only UGa and UGd are excluded. Rear boundary is a "limite ... de fond de terrain" (p.87).
- p.89 (UG8): the general spacing (1/2H min 4 m; H min 8 m; 1.5H min 16 m) applies to UGc;
  UGa, UGb, UGd are excluded. The 8 m and 16 m cases overlap ("l'une des façades" vs "les
  façades ... comportent des vues"): recorded as a `must_flag`.
- p.90 (UG9): 30 % footprint and 8 % annexes apply to UGc; 15 % / 4 % is for UGa and UGd only
  (the trap).
- p.91 (UG10): 7 m eaves/acroterion and 10 m ridge for main buildings apply to UGc; UGa, UGd,
  UGf, UGg are excluded. Ancillary heights 2.50 / 3 m (continues on p.92 with 4.50 m).
- p.94-95 (UG12): 2 spaces per dwelling; bicycle areas for more than three dwellings;
  at least 50 % of required spaces covered or underground (UGa and UGb excluded).

Visual check: pages 80, 86, 88, 89, 90, 91, 94 and 95 were rendered with PyMuPDF and viewed.
The only struck-through value on these pages is the UGa height on p.91 ("7 ~~10~~ mètres à
l'acrotère"), which is not used by this item (UGa is excluded for UGc; the UGa height is
listed as a wrong reading in `must_not`). No UGc figure is struck through. Rendered pages:
[p80](page80.png), [p86](page86.png), [p88](page88.png), [p89](page89.png),
[p90](page90.png), [p91](page91.png), [p94](page94.png), [p95](page95.png).

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[90].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('evals/fixtures/doc/d16_ugc_housing/page91.png')"
```

Brief vs documents: the case brief (trap: 15 % footprint of UGa/UGd applied to UGc) matches
the documents. Setback and spacing statements go beyond the brief focus because the playbook
topics cover them.

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d16_ugc_housing.yaml
OK d16_ugc_housing [doc, verified] facts=16 must_flag=2 must_not=8

uv run python -m evals.gt.pages verify evals/datasets/doc/d16_ugc_housing.yaml
21/21 quotes verified
```
