# d12_ua_chevry_housing source review

Reviewed on 2026-10-17 by a Claude Sonnet source-review pass directly against the supplied
corpus and the original PDF, before running any experiment. No agent output was used as
expected data. One review only: the planned two independent Opus drafts and disagreement
review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
All page numbers are 1-based PDF indices (printed number is one lower).

Scope: chapter `Chevry - UA` (PDF pp.210-221), distinct from `Vallée - UA` (pp.13-30). Site
`z08_chevry` (parcel 91272000AH0198) is in UA of Chevry; its only applying legend item is the
OAP sector. The Chevry UA chapter says nothing about that OAP, so the legend item adds no rule
in the regulation (the OAP document is read by the `oap` task).

- p.215, UA6 / UA7: road: alignment or setback (6.3, no minimum); side: lateral boundary or
  setback of at least the eaves height (7.2), with no distinction by views. 7.1 defines the
  separative limits as lateral and rear but 7.2 names only the lateral limit; no gap is
  flagged because the regulation gives a rule (setback at least the eaves height) for any
  construction not on a boundary.
- p.216, UA8: spacing between buildings at least the eaves height of the taller one, minimum
  4 m without views, 8 m with views.
- p.217, UA9 / UA10: footprint 50 percent of the site (main constructions); height 12 m at
  the eaves, 15 m at the ridge, R+3.
- p.218, UA11: facades of dwellings limited to 25 m in a plane.
- p.219, UA12: 2 spaces per dwelling; at least 50 percent of dwelling spaces in basement or
  ground floor.

Visual check: pages 215, 216, 217 and 219 rendered with PyMuPDF (`import pymupdf`, 1.6x) and
inspected (`page215.png`, `page216.png`, `page217.png`, `page219.png`). No strike-through, no
table or graphic lost in the text layer; the text-layer quotes are the source quotes.

Trap: the Vallée UA chapter has different values (60 percent footprint, 9 m / 12 m,
R+2+combles, alignment mandatory, side 8 m with views / H/2 with 2 m minimum without views,
40 percent covered parking; pp.18-28), listed in `must_not`. Both chapters require 2 spaces
per dwelling, so that figure does not discriminate and is not critical.

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d12_ua_chevry_housing.yaml
uv run python -m evals.gt.pages verify evals/datasets/doc/d12_ua_chevry_housing.yaml
```
