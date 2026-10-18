# d02_uga_height source review

Reviewed on 2026-10-17 by Codex directly against the supplied corpus and original
PDF, before running an experiment. No agent output was used as expected data.
This smoke sample has one manual source review; the planned two independent
Opus drafts and disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
All page numbers below are 1-based PDF indices; printed numbers are one lower.

- Page 90, UG article 9: UGa/UGd footprint is 15% of the terrain in the zone;
  ancillary construction footprint is limited to 4% of the terrain. The general
  UG rule of 30% explicitly excludes UGa.
- Page 91, UG article 10: the text layer reads `7 10 mètres à l’acrotère`.
  Rendered original PDF inspected with `tools.view_image`: **10 is struck
  through, 7 is retained**. The applicable UGa maximum is therefore 7 metres at
  the acroterion. See [rendered page](page91.png). General UG heights explicitly
  exclude UGa. The fixture at `tests/evals/fixtures/items/d02_uga_height.yaml`
  and the example in `evals/README.md` originally reversed the strike-through
  interpretation; both have now been corrected from this inspection.
  `evals/cases/doc.yaml` was already correct.
- Page 94, UG article 12: ordinary habitation requires 2 spaces per dwelling.
  The input specifies ordinary new housing to avoid conflating general parking
  with special residence/social rental rules in the general provisions.

Render command (PyMuPDF's `fitz` import alias):

```powershell
uv run python -c "import fitz; d=fitz.open('ressources/plu_reglement_91272_20210706.pdf'); d[90].get_pixmap(matrix=fitz.Matrix(2,2)).save('data/scratch/doc_d02_page91.png')"
```

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d02_uga_height.yaml
OK d02_uga_height [doc, verified] facts=4 must_flag=0 must_not=3

uv run python -m evals.gt.pages verify evals/datasets/doc/d02_uga_height.yaml
OK plu_reglement p.91 score=1.00
OK plu_reglement p.90 score=1.00
OK plu_reglement p.90 score=1.00
OK plu_reglement p.94 score=1.00
4/4 quotes verified
```

Quote matching verifies the literal text; the height interpretation additionally
depends on the visual inspection recorded above. Keep the text-layer quote with
both values rather than silently creating a quotation absent from that layer.
