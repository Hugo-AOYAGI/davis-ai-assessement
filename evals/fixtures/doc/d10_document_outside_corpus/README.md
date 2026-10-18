# d10_document_outside_corpus source review

Reviewed on 2026-10-17 by a Claude Sonnet worker directly against the supplied corpus
and the rendered original pages, before any experiment. No agent output was used as
expected data. One manual source review; the planned two independent Opus drafts and
disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices (printed number = index - 1).
Site: parcel 91272000BK0007, zone UH (Vallée), wholly inside the PPRi surface
(`evals/datasets/zoning/z04_ppri.yaml`). The zone label is plain `UH`.

- p.6 (Titre I, general provisions): the PPRI was approved on 26 September 2006,
  is a servitude d'utilité publique, its provisions are integrated in piece n°6.3 of
  the PLU and apply to any construction or installation in the sectors concerned.
- p.100 (Vallée UH, article UH2): earth-moving is admitted if compatible with the
  PPRI; "Les constructions édifiées dans les zones à risque d'inondation, doivent
  respecter les règles et conditions fixées dans le Plan de Prévention des Risques
  Inondations." The following bullet opens with "Dans les autres secteurs soumis à un
  risque d'inondations", so its basement / first-floor-level / open-fence conditions
  target flood sectors other than the PPRI ones (the agent must not present them as
  PPRI rules).
- Corpus gap: the PPRI text (piece n°6.3) is in none of the three corpus documents.
  The regulation's Titre III (p.365 onward) lists emplacements réservés, EBC, lexique,
  clay-shrinkage recommendations, plant list, solar-panel sheets and the antenna
  charter, and no PPRI. The OAP mentions flood risk once (p.30, a landscape remark,
  no PPRI rules); the zoning plan only carries the legend label. No PPRI figure can
  be sourced, hence the `must_flag` and the `must_not` on invented figures.
- Not retained as a statement: p.117 (UH article 12, after the UHf rule) says "Dans les
  zones inondables, la couverture des places n'est pas obligatoire." It sits in the UHf
  paragraph, so its scope for a plain UH site is unclear; it is deliberately not scored.

Visual check: p.100 rendered ([page100.png](page100.png)) and p.6
([page6.png](page6.png)); no struck-through text, the text layer is faithful.

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d10_document_outside_corpus.yaml
uv run python -m evals.gt.pages verify evals/datasets/doc/d10_document_outside_corpus.yaml
```

Note: `pages find` is case-sensitive on the pattern against lower-cased text, so use
lower-case search terms (`ppri`, `article uh1`).
