# d04_umg_student_parking_titre1 source review

Reviewed on 2026-10-17 by a Claude Sonnet source review directly against the supplied
corpus and rendered PDF pages, before any experiment. No agent output was used as expected
data. One manual review only; the planned two independent Opus drafts and disagreement
review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices (printed number = PDF index - 1 in the UMG chapter and
Titre I).

Pages reviewed: 4-6 (Titre I), 320-321 (UMG intro, articles 1-2), 327-329 (UMG articles
11-12), 374-379 (lexique).

- p.5 (printed 4), Titre I article 2.2: "Il ne peut être exigé la réalisation de plus d'une
  aire de stationnement par logement pour" the logements locatifs financés avec un prêt aidé
  par l'Etat; the list continues on p.6 with the établissements d'hébergement de personnes
  âgées (L. 312-1 CASF) and the résidences universitaires (L. 631-12 CCH). This is the
  Titre I cap; it is a ceiling on what may be required, not a norm.
- p.327, UMG 12.1: 1 space per 35 m² of floor area within 2 per dwelling; 1 per dwelling for
  State-aided-loan dwellings; 1 per 150 m² for résidences étudiantes.
- p.328-329, UMG 12.3 bicycles (housing norm, no student-residence specific line) and 12.5
  (student residences exempt from the majority-in-basement rule).
- No definition of a "jeunes actifs" / "jeunes travailleurs" residence exists in UMG, Titre I
  or the lexique (p.374-379); text search for `jeune` and `résidence` finds none. Hence the
  `must_flag`. The lexique does not define résidence étudiante either.
- Doubtful point (not asserted as fact): the corpus does not say that "résidences étudiantes"
  (UMG) and "résidences universitaires ... L. 631-12" (Titre I) are the same thing; the
  item only states each quote, which is what the text supports.
- Visual check: pages 5, 6 and 327 rendered and inspected; no strike-through or table
  formatting affects the quoted passages. Renders: `page5.png`, `page6.png`, `page327.png`.

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[326].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save('page327.png')"
```

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d04_umg_student_parking_titre1.yaml
OK d04_umg_student_parking_titre1 [doc, verified] facts=7 must_flag=1 must_not=4

uv run python -m evals.gt.pages verify evals/datasets/doc/d04_umg_student_parking_titre1.yaml
11/11 quotes verified
```
