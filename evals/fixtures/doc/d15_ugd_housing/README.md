# d15_ugd_housing source review

Reviewed on 2026-10-17 by a Claude Sonnet source-review worker directly against the supplied
corpus and the original PDF, before any experiment. No agent output was used as expected
data. This is one manual source review; the planned two independent Opus drafts and the
disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices; printed numbers are one lower.

Site: `evals/datasets/zoning/z13_ugd.yaml` (zone UGd, parcel 91272000BI0058). That item
lists no applying legend item (overlays absent), so `legend_items` is empty.
Per `p.80`, UGd is the sector of the Vallée zone UG that corresponds to the Abbaye.

Input: `aim` and `topics` are the playbook's `rules` task wording; the aim adds one sentence
naming the sector. Only a subset of the topics is scored (footprint, height, setbacks,
spacing, parking).

Reviewed pages and findings:

- p.86 (UG6.3): UGd has its own road rule, building in priority at the current alignment,
  with no distance. The general UG 5 m / 9 m rule is stated "Dans la zone UG".
- p.88 (UG7.2.2): the general setback rule (8 m with views, L=1/2H min 2 m without) excludes
  UGa and UGd. UGa and UGd: L=H min 8 m with views, L=1/2H min 4 m without.
- p.89-90 (UG8.1): spacing between buildings has a separate UGd block: 4 m without views,
  16 m when a facing facade has views (UGa/UGb: 4 m / 8 m; general zone: L=1/2H, L=H, L=1.5H).
  The UGd block is split across the page break, hence two quotes.
- p.90 (UG9.2): UGa and UGd share 15 % footprint and 4 % for annexes; the general 30 % and
  8 % exclude UGa, UGb, UGd.
- p.91-92 (UG10.2): the general 7 m / 10 m height excludes UGa, UGd, UGf, UGg. UGd main
  building: 10 m at eaves or acroterion, 13 m at ridge; annexes 2.50 / 3 / 4.50 m.
- p.94 (UG12.1): housing 2 places per dwelling, no UGd-specific parking norm.

Visual check: pages 86, 88, 89, 90, 91, 92 and 94 were rendered with PyMuPDF and inspected
(`page86.png` ... `page94.png` in this folder). The only strike-through is the `10` in the
UGa line on p.91 (`7 ~~10~~ mètres à l’acrotère`); the UGd block above and below it, and
every other figure used here, is not struck through. The UGa figure is the trap: a reader
mixing the UGa line into UGd would give 7 m.

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[90].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('page91.png')"
```

Validation: `uv run python -m evals.gt.check evals/datasets/doc/d15_ugd_housing.yaml` and
`uv run python -m evals.gt.pages verify evals/datasets/doc/d15_ugd_housing.yaml` both pass
(12/12 quotes verified).
