# d03_aurc_defers_to_ur source review

Reviewed on 2026-10-17 by Claude Sonnet (`claude_sonnet_source_review`) directly against
the supplied corpus and original PDF. No agent output was used as expected data. One manual
source review only; the planned two independent Opus drafts and disagreement review were
not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices; printed numbers are one lower.

Reviewed pages: AURc chapter 184-190 (articles 1-12), UR chapter 149-160 (articles 1-11;
UR6 p154-155, UR7 p156-157, UR8 p157-158, UR9 p158-159, UR10 p159-160).

## Findings

- The brief said articles 10 and 11 defer to UR. The document shows more deferrals, and
  some articles that do NOT defer:
  - Defer to UR ("Les règles applicables sont celles de la zone UR."): AURc3 (p185),
    AURc4 (p186), AURc7 (p188), AURc8 (p188), AURc10 and AURc11 (p189).
  - Do not defer: AURc6 sets its own road setback (5 m / 6 m, p186; UR is 10 m / 14 m
    from the axis, p154-155); AURc9 sets its own footprint, 20 percent (p188; UR is 10
    percent, URa 13 percent, p158); AURc12 sets its own parking (p189).
  - The brief's trap ("AURc sets no height or footprint") is therefore half wrong:
    AURc sets no height (correct) but does set a footprint. The item follows the
    document: footprint is a critical statement with 20 percent and must_not forbids
    both the UR figure and "defers to UR for footprint".
- Height in UR10.2 (p159): 7 m at eaves or acrotère, 10 m at ridge, for main buildings.
  The rendered page shows no strike-through (unlike UGa in d02), see
  [page159.png](page159.png). The AURc footprint page is [page188.png](page188.png),
  also without strike-through.
- The UR text has a double space in "7  mètres" in the text layer; the quote matcher
  normalises it. Nothing is struck in the image.
- UR7 (p156) is internally muddled (general 4 m minimum, then 8 m with windows or 4 m
  without); the item only records the 8 m / 4 m rule of 7.2.2 (non-critical) and no
  `must_flag` was set.
- `legend_items` is empty and no OAP item is listed in the input, as in the brief. The
  AURc chapter makes works subject to the Damiette OAP (AURc1, AURc2), which is read by
  the `oap` task and not evaluated here.

## Validation

```text
uv run python -m evals.gt.check evals/datasets/doc/d03_aurc_defers_to_ur.yaml
OK d03_aurc_defers_to_ur [doc, verified] facts=15 must_flag=0 must_not=6

uv run python -m evals.gt.pages verify evals/datasets/doc/d03_aurc_defers_to_ur.yaml
16/16 quotes verified
```

Render command:

```bash
uv run python -c "import fitz; d=fitz.open('ressources/plu_reglement_91272_20210706.pdf'); d[158].get_pixmap(matrix=fitz.Matrix(1.6,1.6)).save('page159.png')"
```

## Review

Independent review requested two fixes, both applied:

- The side-boundary statement was incomplete: UR7.2.1 (p156) gives half the facade
  height with a minimum of 4 m where there are no windows, 8 m otherwise (with windows).
  The statement and its quotes now cover this (the 4 m alone was not the rule).
- The first `must_not` ("States that AURc has no height rule") could be tripped by the
  correct answer that AURc10 sets no figure of its own and defers to UR. It now reads
  "States that no height limit applies to housing in AURc, or gives ...".

Re-run after the fixes: `evals.gt.check` OK, `pages verify` all quotes verified.
