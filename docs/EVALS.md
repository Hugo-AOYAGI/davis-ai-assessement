# Evals

Evaluation harness and proposed evaluation plan (Part 2 of the brief).

**Current scope:** the repository ships one verified surveyor item,
`evals/datasets/surveyor/s01_joliot_curie.yaml`. The harness supports all four levels, but the
70-item suite below is a plan, not a completed dataset. Zoning, document and end-to-end examples
live in `tests/evals/fixtures/items/` as harness fixtures; they are not runnable benchmark items.
No benchmark results or judge calibration measurements are published yet.

Sections 1 to 6 describe intended coverage and implemented scoring rules. Section 7 gives
commands for the shipped item. Missing datasets and selections with no matching items are errors.

---

## 1. What we evaluate

Three levels. Most items sit at the component level, where runs are cheap and failures are easy to
attribute; the end-to-end level catches what only appears when the pieces are combined.

| Level | Unit under test | Input | Output scored | Planned items |
|---|---|---|---|---|
| Deterministic core | envelope geometry, citation matcher, gate | fixtures | exact values | pytest suite (not counted here) |
| Component | `surveyor` | address | `Site` | 20 |
| Component | `zoning_analyst` | address, program, parcel ids | `ZoneFindings` | 20 |
| Component | `doc_analyst` | task: label, aim, documents, topics, context (zone, legend items, parcel ids, program) | `DocNotes` | 20 |
| End to end | orchestrator + sub-agents + `submit_study` gate | address + program | `VerifiedStudy` + run trace | 10 |

Component inputs are the task text the orchestrator would write (a sub-agent knows nothing
else), filled from ground truth, never from the output of the previous sub-agent, so an upstream
error does not leak into a downstream score. Sub-agents run standalone through `build_subagent(cfg, name)`;
the end-to-end level runs the same graph as the CLI and the server.

What only the end-to-end level sees: reconciling sources (zone from the plan vs the text, OAP
applicability), merging ambiguities from several sub-agents, skipped steps, gate rejections and
retries, and the consistency of the final study.

**Not evaluated**: whether the agent asks the right clarification questions. In evals `ask_user`
is disabled and program facts are supplied in `Case.facts`; regulatory interpretations are never
supplied, the agent must choose and record an `Ambiguity`.

## 2. Eval sets

The target is 70 items, one YAML file each, under `evals/datasets/<level>/`. Only the
surveyor reference item is currently shipped. The remaining cases and ground-truth collection
workflow in this section are planned work.

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

Every item has the same frame; only the input and the kind of expected answer change with the
level.

```yaml
id:          # s01, z03, d07, e01…
level:       # surveyor | zoning | doc | e2e
tests:       # one line: what the item catches
status:      # draft | verified | dropped; only verified items are scored
built_by:    # who wrote the expected answers
input:       # what the unit under test receives
facts:       # expected answers, each with where it comes from (source or evidence)
must_flag:   # points the documents leave open that the output must raise
must_not:    # wrong claims the output must not make
```

**Facts** are scored in code, except `doc_analyst` statements, which the judge matches to notes.
**`must_flag` and `must_not`** are scored by the yes/no judge (section 4).

Fact keys are paths into the output contract of the level (`Site`, `ZoneFindings`, `DocNotes`,
`VerifiedStudy`), resolved by `evals/harness/extract.py`; a key on a `Limit` reads its `value` and
`citations`. Pages are 1-based PDF page indices (the printed page number is one lower in the
regulation).

| Field | Meaning |
|---|---|
| `expect` | exact value after unit normalisation; `null` means "not regulated" |
| `any_of` | the documents leave the point open: any listed value is accepted |
| `expect_none_of` | none of these values may appear |
| `at_least` | minimum number of matching elements |
| `present` / `absent` | legend items that must / must not be reported as applying (`overlays`) |
| `tolerance` | relative tolerance for measured or computed quantities (0.02 = ±2 %) |
| `critical` | the item fails if this fact is not grounded-correct |
| `source` | oracle the value comes from: `ban`, `cadastre`, `gpu_2021`, `geometry`, `hand` |
| `evidence` | pages (and quotes) where the answer lives; quotes are checked by the citation matcher |
| `[field=value]`, `[field~"text"]` | select list elements by exact value / by substring (case and accents ignored) |

Exactly one expectation per fact (`present` and `absent` together count as one). A `verified`
item may not hold an unfilled `<...>` placeholder; drafts may.

#### `surveyor`: scored in code only

```yaml
id: s01_joliot_curie
level: surveyor
tests: address point on unregistered ground beside the CR0249 strip; the real site is CR0247
status: verified
built_by: claude
input:
  address: 4 rue Joliot Curie, 91190 Gif-sur-Yvette
facts:
  - key: choice.parcel_ids
    expect: [91272000CR0247]
    critical: true
    source: hand            # trap: chosen by hand, the parcel is checked to exist in the cadastre
  - key: choice.parcel_ids
    expect_none_of: [91272000CR0249]
    critical: true
  - key: area_m2
    expect: 5952
    tolerance: 0.02
    source: cadastre
  - key: edges[neighbours~"CR0249"]
    at_least: 1             # the site meets the road only across the CR0249 strip
    source: cadastre
```

Random items have the same shape with `source: ban` and no trap fields.

#### `zoning_analyst`: code, plus the judge for `must_flag`

```yaml
id: z01_zone_boundary
level: zoning
tests: site across a zone boundary
status: draft                           # verified once the placeholders are filled
built_by: claude
input:                                  # the task text the orchestrator writes, never upstream output
  address: <address of a site across the UA / UH boundary>
  parcel_ids: [<parcel id>]
  program: housing
facts:
  - key: zone
    any_of: [UA, UH]                    # the plan splits the site: either is accepted
    critical: true
    source: gpu_2021                    # 62 % UA, 38 % UH
  - key: overlays
    present: [Espaces Boisés Classés]   # labels exactly as printed in the plan's legend
    absent:
      - Emplacements réservés pour équipements et aménagements divers, création ou amélioration de voirie
      - Zone de risques d'inondation (PPRi Vallée de l'Yvette approuvé le 26 septembre 2006)
    source: gpu_2021
must_flag:
  - The site lies across a zone boundary (UA / UH)
```

#### `doc_analyst`: statements matched to notes by the judge, quotes checked in code

The output is free-text `DocNotes`, so a fact is a statement. It counts as covered when a note
states it (judge), and as grounded when that note also has a valid citation on one of its evidence
pages (matcher).

```yaml
id: d02_uga_height
level: doc
tests: struck-through "7 10 mètres" (p.91); the height in force is 10 m
status: verified
built_by: claude
input:                                  # the task as the orchestrator writes it (playbook §3)
  label: rules
  aim: the height, footprint, setback and parking limits for housing in sector UGa (Vallée)
  documents: [plu_reglement]
  topics: [height, footprint, setback_road, setback_side, setback_rear, parking]
  context:
    zone: UGa
    legend_items: []
    program: housing
facts:
  - statement: Maximum height in UGa is 10 m at the acroterion
    critical: true
    evidence: [{doc: plu_reglement, page: 91, quote: "10 mètres à l’acrotère"}]
  - statement: Maximum footprint in UGa is 15 % of the site area
    critical: true
    evidence: [{doc: plu_reglement, page: 90, quote: "Dans les secteurs UGa et UGd L’emprise au sol des constructions ne doit pas excéder 15%"}]
  - statement: Housing requires 2 parking spaces per dwelling
    evidence: [{doc: plu_reglement, page: 94, quote: "2 places par logement"}]
must_not:
  - States a maximum height of 7 m in UGa
```

#### End to end: values in code, notes and anti-patterns by the judge

A planned composition helper would pre-fill facts from component items for the same site and
compute the expected envelope with our geometry code. No `evals/gt/compose_e2e.py` helper is
implemented; the example below illustrates the intended format.

```yaml
id: e01_reference
level: e2e
tests: the brief's case; CR0249 strip; "jeunes actifs" undefined in the corpus; Titre I parking cap
status: draft                            # verified once compose_e2e.py has filled the volume
built_by: claude
input:
  address: 4 rue Joliot Curie, 91190 Gif-sur-Yvette
  program: one Résidence Sociale Étudiante and one Résidence Jeunes Actifs, two separate buildings
  facts: []                              # program facts standing in for ask_user answers
from_items: [s01, z05, d01, d11]         # component items the pre-filled facts come from
facts:
  - {key: site.choice.parcel_ids, expect: [91272000CR0247], critical: true}
  - {key: study.regime.zone, expect: UMG, critical: true}
  - {key: study.regime.oap_applicable, expect: true}
  - key: study.envelope.max_height_m
    expect: 20
    critical: true
    evidence: [{doc: plu_reglement, page: 326, quote: "20 mètres"}]
  - key: study.envelope.max_footprint_ratio
    expect: null                         # "not regulated" is the expected answer
    critical: true
    evidence: [{doc: plu_reglement, page: 326}]
  - key: study.admissibility[building~"Sociale Étudiante"].verdict
    expect: permitted
    critical: true
  - key: study.admissibility[building~"Jeunes Actifs"].verdict
    any_of: [permitted, conditional]     # left open by the documents
    critical: true
  - key: envelope.max_volume_m3
    expect: <computed by compose_e2e.py>
    tolerance: 0.02
    source: geometry
must_flag:
  - The destination of a Résidence Jeunes Actifs is not defined by the corpus (housing or hotel-type accommodation)
  - Parking for the student residence is capped by Titre I (p.6), not only by UMG 12 (p.327)
must_not:
  - States a maximum footprint ratio for zone UMG
  - Uses parcel CR0249 as the site
```

The anti-patterns of section 4 are not listed in items: the judge checks them on every end-to-end
study.

| Level | Scored in code | Scored by the judge |
|---|---|---|
| `surveyor` | parcels, area, road frontage | none |
| `zoning_analyst` | zone, overlays present / absent | `must_flag` |
| `doc_analyst` | quotes valid and on an evidence page | statement coverage, `must_not` |
| End to end | values, verdicts, envelope (twice), citations | `must_flag`, `must_not`, anti-patterns |

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

Judge calibration is planned on about 20 notes labelled by hand. The harness has mutation and
validation helpers in `evals/harness/judging/`, tested with fake judge answers, but no calibration
CLI or measured agreement/catch rates are shipped.

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
conf/eval.yaml                # primary config of an eval pass: conf/config.yaml + the eval group
conf/eval/default.yaml        # dataset, item filter, tolerances, intervals, Phoenix, budget, rescore
conf/eval/harness.yaml        # how one item is run (eval.eval_tasks) and judged (eval.judge)
prompts/evals/                # judge system + assertions/reasoning/quality, component task texts
evals/
  datasets/surveyor/s01_joliot_curie.yaml  # the one shipped benchmark item
  harness/
    items.py                  # eval item schema + YAML loader
    tasks.py                  # run e2e, or one sub-agent on its item input -> RunRecord
    extract.py                # fact key -> (value, citations)
    judge.py                  # yes/no Opus judge
    runs/                     # run record, sub-agent message capture, task texts
    judging/                  # judge cache, output views, judge validation
    matching/                 # expectations, values, citation grounding
    scorers/                  # facts, citations, envelope, trajectory, notes
    passes/                   # one pass: scoring of a record, driver + budget, Phoenix, files
    report/                   # Wilson and bootstrap intervals, per-level aggregates, summary.md
  run.py                      # Hydra entrypoint
tests/evals/                  # harness unit tests on canned outputs and fake runs, offline
```

- `evals/` is a top-level package: it imports `agent.*`, nothing in `agent` imports it. The judge
  model is a `models.nodes.judge` entry built by `agent.llm`, like every other model.
- Config is composed by the same loader as the server and CLI (`load_config(overrides,
  config_name="eval")`; `evals.run` is a Hydra main on the same `conf/eval.yaml`): the agent
  config plus the `eval` group, with `ask_user` disabled. Any agent knob can be overridden next
  to the eval ones.
- For each item, the pass runs the unit under test (`run_item`), saves its record to
  `records/<item_id>.json` at once, then scores it: facts, citations, envelope (e2e), trajectory,
  judge questions, item pass. The same code scores offline and under Phoenix.
- With `eval.phoenix.enabled` (default), each level's items are uploaded as a dataset named
  `<level>-<content hash>` (editing ground truth creates a new dataset; an existing one is reused)
  and run as one Phoenix experiment whose task runs and scores an item, so its traces sit next to
  its scores. Evaluators: `item_pass`, `grounded_accuracy`, `answer_accuracy`,
  `citation_validity`, `must_flag_rate`, `must_not_hits`, `anti_patterns`, `cost_usd`.
  `eval.phoenix.enabled=false` runs the same pass without Phoenix (`eval.concurrency` items at a
  time).
- Budget guard: no item is launched once agent runs plus judging reach `eval.max_cost_usd`;
  those items are listed as not launched.
- If Phoenix finishes without an item's scores for a reason other than the budget, the pass
  raises an error instead of publishing a report with that item omitted.
- `eval.rescore=<run dir>` scores that pass's saved records again against the current items and
  scorers, without running any agent (judge answers are cached).
- The record is `outputs/evals/<date>/<time>/`: `scores.json` (per level: pass rate with a Wilson
  interval, grounded and answer accuracy with bootstrap intervals over items, luck rate, citation
  validity, `must_flag` coverage, `must_not` and anti-pattern hits, trajectory figures, cost; per
  item: every score), `summary.md` (one table per level, the failed items with their failing
  critical facts) and `records/`. Publishing selected results under `docs/evals/` is planned;
  no such result archive is currently shipped.

```bash
uv run phoenix serve                                         # http://localhost:6006
uv run python -m evals.run eval.dataset=surveyor
uv run python -m evals.run eval.dataset=surveyor eval.items=[s01_joliot_curie] eval.phoenix.enabled=false
uv run python -m evals.run eval.rescore=outputs/evals/<date>/<time>   # re-score, no agent run
```

The eval commands require the project environment, API credentials and ingested corpus described
in the README. Start Phoenix for the default mode, or use `eval.phoenix.enabled=false` to run
without its server. This still runs the agent and may use paid API calls. Judge answers are
reused only when the resolved model settings, structured-output method, prompts and inputs match
the cache.

## 8. Planned budget

The proposed full-suite budget is $50 of API credit, with at most $10 while building the harness.
The estimates below are projections for the planned 70-item suite, not measured spending. Ground-truth drafting
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
