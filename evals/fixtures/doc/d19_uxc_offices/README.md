# d19_uxc_offices source review

Reviewed on 2026-10-17 by Claude Sonnet directly against the supplied corpus and
the original PDF, before any experiment. No agent output was used as expected
data. One source review only: the planned two independent Opus drafts and the
disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices; printed numbers are one lower.

Reviewed pages: 167-183 (chapter "Vallée - UX", articles UX1 to UX16), text and
rendered images for 168, 174, 176, 177, 178, 180, 181. No strike-through on any
of them.

- p.167: UXc is the sector for activities compatible with the pavillonnaire
  character of the neighbouring districts.
- p.168, article UX1 table ([page168.png](page168.png)): the text layer lists
  the row labels and the word "interdit" without column positions. The rendered
  table shows "Bureaux, services" forbidden under UX and UXe only; UXa, UXb and
  UXc are empty. UXc forbids only "Hôtellerie, restauration" and "Recherche".
  This is the trap: collapsing UXc into UX would forbid offices. Article UX2
  allows housing only for caretaking of the authorised activities.
- p.171: accesses (3.2.2); p.173: stormwater flow 0.7 l/s/ha (4.2.2).
- p.174 (UX6): 10 m road setback "En UX, UXc et UXe".
- p.175-176 (UX7): side and rear boundaries; free on the boundary or L=1/2 H
  with minimum 6 m "Dans la zone UX, UXc et UXe". One rule for all boundaries,
  no distinction with or without windows.
- p.177 (UX8): between buildings 1/2 H min 6 m (no vues) or H min 8 m (vues).
- p.178 ([page178.png](page178.png)): UX9 footprint UXc 80% activities / 40%
  housing; UX10 UXc 9 m and R+2 (UX and UXe: 7 m, R+1).
- p.180-181 (UX12): offices 1 place per 30 m2 in UX, UXc, UXe (UXb: 50 m2);
  bicycles for offices 1.5% of floor area created.

Disagreements with the case brief: none. The zoning item z09_uxc has no
legend items (overlays absent), so `legend_items` is empty. The parcel id is
91272000CC0080.

Render command:

```powershell
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[167].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('evals/fixtures/doc/d19_uxc_offices/page168.png')"
```

## Review

Independent review by the coordinator: all statements confirmed except the stormwater fact (p.173), which omitted that the 0.7 l/s/ha discharge rate applies only when infiltration is demonstrably impossible ("en cas d impossibilite demontree"); otherwise infiltration on the plot is required. The statement now carries that condition, with a second quote. Checks re-run after the change: `evals.gt.check` and `pages verify` pass.
