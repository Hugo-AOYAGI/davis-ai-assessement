# d01_ua_vallee_vs_chevry source review

Reviewed on 2026-10-17 by Claude Sonnet directly against the supplied corpus and original
PDF, before any experiment. No agent output was used as expected data. This item has one
manual source review; the planned two independent Opus drafts and disagreement review were
not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
All page numbers are 1-based PDF indices (printed number = index - 1 in the Vallée chapter).

The regulation holds two chapters with a zone called UA: "Vallée - UA" (PDF p.13-30) and
"Chevry - UA" (PDF p.210-221). The input names the Vallée chapter; the Chevry values are the
trap.

Pages reviewed (Vallée - UA), with the values retained:

- p.18, UA6 (road): in UA, constructions at the current or projected alignment. Sectors
  UAa/UAb/UAc/UAd have their own lines; the item concerns plain UA.
- p.20, UA7 (side): in UA, on the boundaries within 30 m of the alignment, only annexes
  beyond; setback (7.2.2, all sectors) 8 m with views, H/2 with a 2 m minimum without views.
- p.22, UA9 (footprint): in UA, 60% of the terrain, annexes included.
- p.23, UA10 (height): in UA, UAa, UAb, UAd, 9 m at the eaves or acroterion, 12 m at the
  ridge, R+2+combles (when the graphic document does not regulate it).
- p.27-28, UA12 (parking): 2 places per dwelling; 40% covered or underground (not in
  flood-prone zones).

Chevry - UA values used only for `must_not` (p.215-219): road at the alignment or set back
(6.3); side setback equal to the eaves height (7.2); footprint 50% of the terrain, main
buildings only (9.2); height 12 m at the eaves, 15 m at the ridge, R+3 (10.2); 2 places per
dwelling (same value as Vallée, so not a discriminator) with at least 50% of the housing
spaces in basement or ground floor (12.1).

Visual check: pages 18, 20, 22, 23 and 27 rendered with PyMuPDF at 1.6x
([p18](page18.png), [p20](page20.png), [p22](page22.png), [p23](page23.png),
[p27](page27.png)) and inspected: no strike-through or struck value on the retained rules, so
the text layer is reliable. The 9 m figure (p.23) is the first of the two heights listed.
Brief and documents agree; the case brief gave no values, only the Chevry trap, which matches
p.217.

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[22].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('evals/fixtures/doc/d01_ua_vallee_vs_chevry/page23.png')"
```

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d01_ua_vallee_vs_chevry.yaml
uv run python -m evals.gt.pages verify evals/datasets/doc/d01_ua_vallee_vs_chevry.yaml
```

Both pass (11/11 quotes verified).
