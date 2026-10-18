# e10_n_housing source review

Reviewed on 2026-10-17 by Claude (Sonnet) against the corpus, the cadastre and the component
items, before any experiment. No agent output was used. One manual source review only; the planned
two independent Opus drafts and human sign-off were not performed.

## Sources

- Site: BAN row `91272_1370_00016` (16 Impasse de la Gourdillerie, point 2.11645, 48.70236) lies
  inside cadastral parcel `91272000CC0193` (0.0 m in `evals.gt.site near`). Parcel check:
  `evals.gt.site parcel 91272000CC0193` gives contenance 113 m2, polygon area 129.4 m2, 14 m of
  frontage on unregistered ground. Neighbours CC0199 (112 m2, 2.1 m away), CC0198, CC0152 and
  CC0201 are not the BAN target. No surveyor item exists; the parcel comes from
  `z07_natural_zone` (fixtures `evals/fixtures/zoning/z07_natural_zone.*`, archived 2021 GPU export).
- Zone and overlay: `z07_natural_zone`: LIBELLE `N`, no sub-sector, full-parcel intersection; the
  emplacement réservé (turning area) covers about 58% of the parcel, no EBC, PPRi or wetland.
- Prohibition: `d20_n_housing` and `evals/fixtures/doc/d20_n_housing/README.md`. Regulation PDF
  (`plu_reglement`, 1-based pages): p193 article N1 forbids new housing in the whole zone N and its
  sectors "autres que ceux admis en N2"; p194 article N2 admits no new dwelling zone-wide, only the
  extension of existing dwellings (15% of floor area). Both quotes were checked with
  `evals.gt.pages verify` (score 1.00).

## Facts

- Critical: parcel CC0193 (cadastre, BAN point inside); zone N (gpu_2021); verdict `prohibited`
  for the new house (N1 + N2).
- Non-critical: the emplacement réservé applies (gpu_2021); site area 129.4 m2, 2% tolerance, from
  the cadastre polygon (the contract's `Site.area_m2` is the polygon area; the declared contenance
  of 113 m2 differs by 13% and is not accepted).
- The verdict key `study.admissibility.verdict` reads every admissibility entry, so a study with
  several entries must have them all `prohibited`; the program has one building.

## Limits

- No envelope or proposal-volume fact: the program is prohibited, so there is no expected
  buildable envelope; delivering one is covered by `must_not`.
- Contract limitation: `Study` expresses the refusal (`Verdict.PROHIBITED`), but
  `submit_study` requires an architect `envelope` artifact whose `EnvelopeRules` need a positive
  `max_height_m` per building. Plain zone N does not regulate height (N10), so a clean prohibited
  study may be impossible to complete through the current gate. The item scores the study
  fields only; whether the agent can finish this path is a finding of the experiment.
- Parcel is tiny (about 129 m2); N6/N7 setbacks (12 m from the road axis, 16 m from boundaries)
  would exceed it, but this is a secondary observation, not asserted.
- Possible N2 exceptions (agricultural or forestry buildings, extension of an existing dwelling)
  are not ruled out by the program text; the item does not assert whether an existing dwelling
  stands on CC0193.
