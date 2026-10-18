# d17_uca_housing source review

Reviewed on 2026-10-17 by Claude (Sonnet) directly against the supplied corpus and original
PDF, before any experiment. No agent output was used as expected data. One manual source
review only; the planned two independent Opus drafts and disagreement review were not performed.

Source: `ressources/plu_reglement_91272_20210706.pdf` (corpus id `plu_reglement`).
SHA-256: `e2a2450aa9670774eb6f5e377f26d4301a7902206507a9b4f4d9651ae07a0405`.
Page numbers are 1-based PDF indices; printed numbers are one lower.

Naming: the regulation has no zone "UCa" chapter of its own. The sector UCa (quartier de
l'Abbaye) is a sector of zone UC, chapter "Vallée - UC" (PDF p.48-62). The brief's zone `UCa`
is therefore read as UC, sector UCa.

Pages reviewed (rendered images in this directory: page54, 55, 56, 57, 58, 62):

- p.54, UC6: UCa 8 m from the alignment / 12 m from the road axis; general UC is 5 m / 9 m.
- p.55-56, UC7: UCa side/rear setback L=H min 8 m with views; L=1/2H min 4 m without views and
  with a facade under 15 m. General UC is L=1.5H / L=H. The regulation is silent for a UCa
  facade without views of 15 m or more: recorded as `must_flag`.
- p.56-57, UC8: UCa and UCb share one spacing rule (L=H min 8 m with views; height of the lower
  building min 8 m without views); the general UC rule (1.5H min 16 m...) is excluded.
- p.57, UC9: UCa 25 % (general UC 30 %, UCb 20 %).
- p.58, UC10: UCa 15 m ridge, 12 m eaves/acroterion, R+3+C (general UC 13 m / 10 m).
- p.62, UC12: housing 1 space per 35 m² of floor area, capped at 2 per dwelling; 40 % covered.
  (The "2 places par logement" flat norm belongs to chapter UG, not UC.)

Visual check: every page above was rendered at 1.6x and inspected. No strike-through or
other formatting lost in the text layer; the text-layer quotes match the images. UCb and
general-UC figures appear only in `must_not`.

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d17_uca_housing.yaml
OK d17_uca_housing [doc, verified] facts=13 must_flag=1 must_not=5

uv run python -m evals.gt.pages verify evals/datasets/doc/d17_uca_housing.yaml
13/13 quotes verified
```

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/plu_reglement_91272_20210706.pdf'); d[53].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save('page54.png')"
```

## Review

Independent review found that UC12.5 (PDF p.63, printed 62) overrides the article 12.2
housing norm for new grouped operations: "il sera exigé 3 places par logement et 1 place
« visiteurs » pour 3 logements" (opérations d'ensemble: lotissement, permis groupés). For other
new constructions 12.5 sends back to 12.2. Fixes: the 1-per-35 m² / cap-2 fact is now qualified
"outside opérations d'ensemble"; a new fact records the 3 + visitors rule with its quote; the
parking `must_not` also forbids ignoring that rule. The p.63 text was read; the quote matches.
Whether the program is an opération d'ensemble is not given in the input, so either norm
reading, correctly conditioned, is acceptable. Item now has 13 facts.
