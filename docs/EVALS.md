# Evals

How we prove the agent is correct (Part 2 of the brief). Sections 1–5 answer the brief's
questions: what we evaluate, how the eval sets are built, how they are scored, why they are hard
to game. Results and failure modes (sections 9–10) are filled in from the scored pass.

---

## 1. What we evaluate

Three levels. Most items sit at the component level, where runs are cheap and failures are easy to
attribute; the end-to-end level catches what only appears when the pieces are combined.

| Level | Unit under test | Input | Output scored | Items |
|---|---|---|---|---|
| Deterministic core | envelope geometry, citation matcher, gate | fixtures | exact values | pytest suite (not counted here) |
| Component | `surveyor` | address | `Site` | 20 |
| Component | `zoning_analyst` | seeded `Site` | `ZoneFindings` | 20 |
| Component | `doc_analyst` | task + seeded `Site` and `ZoneFindings` | `DocNotes` | 20 |
| End to end | orchestrator + sub-agents + `submit_study` gate | address + program | `VerifiedStudy` + run trace | 10 |

Component inputs are fixtures, never the output of the previous sub-agent, so an upstream error
does not leak into a downstream score. Sub-agents run standalone through `build_subagent(cfg, name)`;
the end-to-end level runs the same graph as the CLI and the server.

What only the end-to-end level sees: reconciling sources (zone from the plan vs the text, OAP
applicability), merging ambiguities from several sub-agents, skipped steps, gate rejections and
retries, and the consistency of the final study.

**Not evaluated**: whether the agent asks the right clarification questions. In evals `ask_user`
is disabled and program facts are supplied in `Case.facts`; regulatory interpretations are never
supplied, the agent must choose and record an `Ambiguity`.

## 2. Eval sets

70 items, one YAML file each, under `evals/datasets/<level>/`.

### End to end (10)

Cases vary the site (sector, zone, sub-sector) and the program.

| # | Site | Program | What it tests |
|---|---|---|---|
| e01 | 4 rue Joliot Curie (UMG, Moulon) | RSE + Résidence Jeunes Actifs | the brief's case; CR0249 strip trap; "jeunes actifs" undefined in the corpus; Titre I parking cap |
| e02 | same site | public-interest facility | 25 m height; UMG 13 green-space rules do not apply |
| e03 | same site | offices | 18 m "other uses" height; different parking |
| e04 | Moulon UM4 / UM5 | housing | heights set per sub-sector |
| e05 | Vallée UA | housing | 60 % footprint; 9 m / 12 m; alignment; H/2 setbacks |
| e06 | Chevry UA | housing | same zone code as e05, different values (50 %, 12 m / 15 m) |
| e07 | Vallée UGa | housing | 15 % footprint; struck-through "7 10 mètres" (p.91) |
| e08 | Chevry UH | housing | 1/3 footprint; 4 m road setback; 2 / 4 / 6 m side setbacks; non-trivial envelope |
| e09 | AURc (Damiette) | housing | articles 10–11 defer to zone UR; OAP chapter 4 |
| e10 | N or A zone | housing | negative case: housing prohibited or restricted |

### `surveyor` (20)

- 10 traps, labelled by hand: the reference address (point on unregistered ground, 1.8 m from the
  116 m² CR0249 strip, 2.5 m from the real site CR0247), corner plot, site spanning several parcels,
  landlocked plot, address point on a road, hamlet address, street name shared with a neighbouring
  commune, unknown address (must fail cleanly), and the e01–e10 sites not covered above.
- 10 random addresses drawn from the BAN addresses that link a parcel, spread over Vallée, Chevry
  and Moulon.

### `zoning_analyst` (20)

- 10 traps: site near a zone boundary, inside an EBC, inside the PPRi, on an emplacement réservé, on
  a protected retail frontage, in an OAP sector, in an N zone, in Chevry, in UXc, and a site where
  the online zoning and our plan disagree.
- 10 sites spread over about 10 different zones and sub-sectors.

### `doc_analyst` (20)

- 10 trap tasks: Vallée UA vs Chevry UA; UGa struck-through height; AURc → UR; Titre I parking cap
  for student residences; public-interest exceptions in UMG; green roofs (lexique counts them at
  0.5, UMG 13 does not count them); OAP Joliot Curie applies (with chapter 7); site outside every
  OAP perimeter; a rule that points to a document outside the corpus (must be flagged); a repealed
  article (articles 5 and 14).
- 10 zone × program tasks with real numeric limits across the three sectors.

### Item format

Two parts: **facts**, scored in code, and **notes**, scored by a yes/no judge.

```yaml
id: e01_reference
level: e2e
status: verified                  # draft | verified; only verified items are scored
reviewed_by: hugo
input:
  address: 4 rue Joliot Curie, 91190 Gif-sur-Yvette
  program: one Résidence Sociale Étudiante and one Résidence Jeunes Actifs, two separate buildings
  facts: []                       # program facts standing in for ask_user answers

facts:
  - key: site.parcel_ids
    expect: [91272000CR0247]
    critical: true
  - key: site.area_m2
    expect: 5952                  # measured value: ±2 %
  - key: regime.zone
    expect: UMG
    critical: true
  - key: envelope.max_height_m
    expect: 20
    critical: true
    evidence:                     # where the answer lives; every quote is checked by the matcher
      - {doc: plu_reglement, page: 326, quote: "20 mètres"}
  - key: admissibility.residence_jeunes_actifs.verdict
    any_of: [permitted, conditional]   # left open by the documents: either is accepted
  - key: envelope.max_footprint_ratio
    expect: null                  # "not regulated" is the expected answer
    evidence: [{doc: plu_reglement, page: 326}]

notes:
  must_flag:
    - The destination of a Résidence Jeunes Actifs is not defined by the corpus (housing or hotel-type accommodation)
    - Parking for the student residence is capped by Titre I (p.6), not only by UMG 12 (p.327)
  must_not:
    - States a maximum footprint ratio for zone UMG
    - Uses parcel CR0249 as the site
```

Fact keys are paths into the scored output, resolved by `evals/harness/extract.py`. Pages are
1-based PDF page indices (the printed page number is one lower in the regulation).

For `doc_analyst`, whose output is free-text `DocNotes`, a fact is a statement (e.g. "housing
height in UMG is 20 m") plus its evidence pages; it is scored as covered by a note (section 4).

## 3. Building ground truth

Ground truth comes from an **oracle independent of the agent's own tools** where one exists, and
from Opus drafts checked in code where none does. Nothing is copied from agent output.

| Level | Inputs chosen by | Expected answer from | Checks |
|---|---|---|---|
| `surveyor` | traps by hand; random items from the BAN export (commune 91272) | random items: BAN `cad_parcelles` (independent of the agent's geocoder + nearest-parcel search); traps: by hand; area and polygon from the cadastre (API Carto) | parcel exists in the cadastre; polygon saved as a fixture |
| `zoning_analyst` | traps by hand; spread over zones | Géoportail de l'Urbanisme, archived 2021-07-06 export: zone label, sub-sector, surface prescriptions (EBC, OAP, emplacements réservés, PPRi, zones humides), mapped to the plan's legend labels | oracle vs our plan checked by eye where they disagree |
| `doc_analyst` | trap list + zone × program grid | two independent Opus drafts from the corpus pages | quotes verified by the citation matcher; drafts diffed; disagreements reviewed |
| End to end | the 10 cases above | composed from the component answers for the same site; **envelope computed by our geometry code** from the expected parameters and the cadastre polygon; notes drafted by Opus | as above, and notes read by a human |

- **Drafting**: Opus runs in separate Claude Code threads (subscription, not API budget), each with
  the same brief (`prompts/evals/draft_ground_truth.md`) and page ranges, without seeing the other
  draft. `evals/gt/diff.py` lists disagreements and runs the citation matcher on every quote.
- **Review** is light: disagreements and failed quotes first, then the end-to-end notes.
- **Oracle caveats**:
  - BAN links a parcel for only 30 % of Gif addresses (none on rue Joliot-Curie), so random
    `surveyor` items are drawn only from linked addresses and traps are labelled by hand.
  - The GPU API serves the PLU in force (`91272_PLU_20260408`), not the 2021-07-06 corpus. The
    zoning oracle is therefore the **archived 2021-07-06 CNIG export** (`ZONE_URBA` and
    `PRESCRIPTION_SURF` shapefiles, EPSG:2154), downloaded from the GPU archive of
    `91272_PLU_20210706`; its zoning plan and OAP PDFs are byte-identical in size to ours. For
    reference, the 2026 version differs only in three Moulon areas (UM3 → NE, UME → NE,
    UM5 → UM5b); surface prescriptions are unchanged.
  - The GPU labels every OAP perimeter generically; Joliot Curie and Moulon are told apart by
    geometry.

## 4. Scoring

### Facts

Each fact gets two scores:

- **answer-correct**: the value matches.
- **grounded-correct**: the value matches, and at least one of its citations is valid (the quote is
  found on the cited page by the citation matcher) and sits on one of the fact's evidence pages.

The headline metric is **grounded accuracy**. The gap between answer accuracy and grounded accuracy
is the **luck rate**: right answers the agent did not justify from the right source.

**Tolerances**

- Values read from the documents (heights, setbacks, ratios, parking ratios, storeys): exact, after
  unit normalisation (20 % = 0.2). `null` means "not regulated" and must be stated as such.
- Measured or computed quantities (site area, footprint, volume): ±2 %.
- Points the documents leave open list every acceptable answer (`any_of`); anything else, including
  hedging between values, is wrong.

**Envelope, scored twice**: against the expected envelope, and against the envelope our geometry
code recomputes from the agent's own parameters. The first measures the whole chain; the second
separates "wrong rule" from "wrong calculation".

### Citations

Deterministic only. A citation is **valid** when the citation matcher finds its quote on the cited
page (normalised text, fuzzy score ≥ 0.9, every number in the quote present on the page). The
plan's raster citations are counted as valid when they name the right legend item. Reported: share
of valid citations, and share of facts with a valid citation on an expected page.

### Notes and anti-patterns (judge)

A yes/no judge (Opus 5.5, prompts in `prompts/evals/`) answers one question per call, with a short
reason. No 1–10 scores.

- `must_flag`: is this expected ambiguity raised by one of the recorded ambiguities or open points?
- `must_not`: does the output make this forbidden claim?
- `doc_analyst` coverage: does a note state this expected fact? (grounded if that note also has a
  valid citation on an expected page)
- Anti-patterns, checked on every end-to-end study:
  1. **Hedging**: several values for one limit without committing, outside a recorded ambiguity.
  2. **Deferral**: sends the reader elsewhere ("check with the town hall") when the corpus answers.
  3. **Invented rule**: a limit or condition that none of its citations contains.
  4. **Restating without applying**: rule text copied but never applied to the site or program.
  5. **Inconsistency**: the summary or report contradicts the typed fields.
  6. **Unflagged gap**: a rule pointing outside the corpus treated as known.

The judge is validated once on about 20 notes labelled by hand: we report its agreement rate and its
yes-rate on deliberately wrong outputs.

### Trajectory

From the run record: whether the expected sections were actually read (a tool call on the article
or page before the value was stated), gate rejections and retries, tool calls, cost, wall time.

### Item pass

An item **passes** when every `critical` fact is grounded-correct and no `must_not` is violated.
Critical facts are the parcel, zone, admissibility verdicts, and the height and footprint limits.
Grounded accuracy is reported next to it.

## 5. Why these evals are hard to game

- **Independent ground truth**: oracles (BAN, GPU) and Opus drafts, never the agent's own output.
- **Traps and negative items** where the obvious answer is wrong: CR0249, the struck-through
  height, Vallée vs Chevry UA, an N-zone address, rules pointing outside the corpus.
- **Grounded scoring**: a right value without a valid citation on the right page does not count,
  and fabricated quotes fail the matcher.
- **No credit for hedging**: several answers are accepted only where the documents leave the point
  open and the ambiguity is recorded.
- **`must_not` notes and anti-pattern checks** penalise invented limits, deferral and
  inconsistencies.
- **The envelope is recomputed** from the agent's own parameters, so a plausible volume with wrong
  inputs is caught.

## 6. What the numbers can and cannot say

10 end-to-end cases give wide intervals on an item pass rate (7/10 has a 95 % Wilson interval of
about [0.40, 0.89]). The unit that carries the statistics is the fact (about 250 across all
levels); since facts within an item are correlated, grounded accuracy is reported with a bootstrap
interval over items. Pass rates are reported with Wilson intervals. We claim no difference smaller
than the interval. The end-to-end level measures how the pieces fit together, and each trap item
works as a test of one capability; neither is meant as a precise rate.

## 7. Harness

```
conf/eval/default.yaml        # dataset, judge, Phoenix endpoint, tolerances
prompts/evals/                # judge prompts, ground-truth drafting brief
evals/
  datasets/{e2e,surveyor,zoning,doc}/*.yaml
  drafts/                     # the two independent drafts per item, kept for audit
  fixtures/sites/             # seeded Site and ZoneFindings inputs
  harness/
    items.py                  # eval item schema + YAML loader
    tasks.py                  # run e2e, or one sub-agent on seeded inputs
    extract.py                # fact key -> (value, citations)
    scorers/                  # facts, citations, envelope, trajectory, notes
    judge.py                  # yes/no Opus judge
    report.py                 # scores.json + summary.md
  gt/                         # sample_addresses, oracle_site, oracle_zoning, diff, compose_e2e
  run.py                      # Hydra entrypoint
tests/evals/                  # scorer unit tests on canned outputs, offline
```

- `evals/` is a top-level package: it imports `agent.*`, nothing in `agent` imports it. The judge
  model is a `models.nodes.judge` entry built by `agent.llm`, like every other model.
- Config is composed by the same `load_config(overrides)` as the server and CLI, so any agent knob
  can be overridden for an eval run.
- Each run uploads the dataset to Phoenix (named by content hash, so ground-truth edits create a new
  version) and runs a Phoenix experiment: one task per level, scorers as evaluators. Phoenix is the
  UI for browsing traces and per-item results.
- The record is `outputs/evals/<date>/<time>/scores.json` and `summary.md`; the final ones are
  copied to `docs/evals/` so this document does not depend on a local Phoenix database.

```bash
uv run phoenix serve                                    # http://localhost:6006
uv run python -m evals.run eval.dataset=surveyor
uv run python -m evals.run eval.dataset=e2e models.nodes.orchestrator.effort=low
```

## 8. Budget

$50 of API credit for evals, of which at most $10 while building the harness. Ground-truth drafting
uses a Claude subscription, not API credit. Each item runs once per pass.

| Level | Items | Cost per item | Per pass |
|---|---|---|---|
| End to end | 10 | ~$0.75 | ~$7.50 |
| `surveyor` | 20 | ~$0.02 | ~$0.40 |
| `zoning_analyst` | 20 | ~$0.06 | ~$1.20 |
| `doc_analyst` | 20 | ~$0.30 | ~$6 |
| Judge | | | ~$1–2 |
| **Total** | 70 | | **~$15–17** |

## 9. Results

_To be filled from the scored pass: grounded and answer accuracy per level with intervals, item pass
rates, citation validity, `must_flag` coverage, `must_not` and anti-pattern hits, trajectory
figures, cost._

## 10. Failure modes

_To be filled from the scored pass, with the items that exposed each failure._

## 11. Open decisions

- Keep the "evidence page" condition in grounded-correct (deterministic) or only check that the
  quote is valid.
- Final anti-pattern list and judge prompts.
