# d13_um4_housing source review

Reviewed on 2026-10-17 by Claude Sonnet directly against the supplied corpus and original
PDF. No agent output was used as expected data. One manual source review only; the planned
two independent Opus drafts and disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices (printed number is one lower).

Site: `evals/datasets/zoning/z16_um4.yaml` (parcel 91272000CP0123, zone UM4, OAP sector
legend item). Reviewed pages: 306-319 (zone UM chapter: UM3/UM4/UM5 sectors, articles 1-16).

- p.306: zone UM is split into UM3, UM4, UM5 (height variations); Joliot-Curie is a separate zone (UMG, p.320+).
- p.313, article 10: UM4 housing 20 m with R+5; other destinations 18 m. UM3 is 15 m, UM5
  housing 20 m R+5, UM5 other 24 m, UM5a hotel 31 m (the trap values).
- p.312, article 9: footprint not regulated. p.310-311 article 6: alignment or setback >= 1 m.
  p.311 article 7: boundaries (vues: H/2 up to 12 m with min 5 m, 6 m above 12 m; no vues 3 m).
  p.312 article 8: 10 m with vues, 3 m without.
- p.315 article 12.1: housing 1 space per 35 m2 of floor area, capped at 2 per dwelling; 1 per
  dwelling for State-aided loans; student residences 1 per 150 m2. p.316 bikes; p.317 85% integrated.
- p.318 article 13.3: 20% green space, 10% deep soil.

Strike-through check: pages 311, 312, 313, 315, 317, 318 rendered with PyMuPDF and inspected
(`page311.png` ... `page318.png`); no struck-through text on any of them.

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[312].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('evals/fixtures/doc/d13_um4_housing/page313.png')"
```

Validation: `evals.gt.check` OK; `evals.gt.pages verify` 21/21 quotes verified.

Note: the playbook topic list is used in full (13 topics); statements cover the focus topics
(height, footprint, setbacks, spacing, parking, green space, definitions, OAP compatibility).
