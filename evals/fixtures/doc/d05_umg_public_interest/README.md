# d05_umg_public_interest source review

Reviewed on 2026-10-17 by Claude Sonnet (Sample worker) directly against the supplied
corpus, before any experiment. No agent output was used as expected data. One source
review only: the planned two independent Opus drafts and disagreement review were not
performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices; printed numbers are one lower. Pages read in full:
320-332 (zone UMG, "Zone UMG - Joliot-Curie", sector Moulon).

- Page 326, UMG article 10.2: 25 m for constructions of main destination "service public
  ou d'intérêt collectif"; 20 m and R+5 for main destination housing; 18 m for any other
  destination. Rendered page inspected: no strike-through or table, text layer is faithful
  ([page326.png](page326.png)). Trap neighbour: sector UM4 (p.313) gives 20 m to public
  service / collective-interest constructions, a different zone and not applicable to UMG.
- Page 326, UMG article 9: footprint "n'est pas réglementée" (compatibility with the OAP,
  document 3, is required but fixes no ratio in the regulation).
- Page 331, UMG article 13.3: 20 % green space, 10 % open ground, trees per 300 m2 for new
  construction, but the quantitative provisions "ne sont pas applicables aux constructions
  et installations nécessaires aux services publics ou d'intérêt collectif". Rendered page
  inspected, no strike-through ([page331.png](page331.png)). The 13.1 definition of green
  space (p.330) is therefore not needed for the facility.
- Page 328, article 12.1: parking for public service / collective-interest constructions is
  set case by case; only higher education and research has a ratio (1 per 170 m2).
- Pages 324-325, articles 6, 7, 8: road alignment or 1 m setback; boundaries 6 m with vues,
  3 m without, building on the boundary allowed; 10 m / 6 m between buildings on one plot.
  Kept as non-critical statements because the playbook topic list covers them.

Terminology: the case brief says "équipement d'intérêt collectif"; the regulation says
"service public ou d'intérêt collectif" for UMG. They are treated as the same destination;
no must_flag because the corpus does not leave the rule open.

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d05_umg_public_interest.yaml
uv run python -m evals.gt.pages verify evals/datasets/doc/d05_umg_public_interest.yaml
```

## Review

Independent review found the reference site (4 rue Joliot Curie, parcel 91272000CR0247,
item `z01_joliot_curie`) lies in the OAP perimeter. `input.context` now lists the legend
item exactly as z01 does ("Secteur à Orientation d'Aménagement et de Programmation") and
the parcel id, like d04. No fact changes: UMG articles 1-4 and 6-13 only require
compatibility with the OAP (document 3) and the règlement fixes no OAP-specific limit, so
the 25 m height, the article 13 exemption and the unregulated footprint stand. The `rules`
task reports only what the règlement says about the perimeter; OAP content belongs to the
`oap` task.
