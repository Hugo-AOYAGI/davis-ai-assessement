# Evaluations

The benchmark has **70 source-checked items**: 20 surveyor, 20 zoning, 20 document and
10 end-to-end. [Dataset provenance](datasets/README.md) describes construction, review and
coverage. `verified` means source/schema review by model workers, not human sign-off.

The [historical report](../handoff/evaluation.html) compares three configurations from
18 October 2026. Retained score/configuration snapshots live in
[`handoff/evaluation/`](../handoff/evaluation/README.md). Those results predate submission
cleanup; do not present them as newly measured results for changed code.

## 1. What runs

Component items invoke one configured specialist graph with the kind of task the
orchestrator delegates. End-to-end items invoke the unattended study workflow. Ground truth
comes from retained sources, not outputs of the agent under test.

| Level | Output | Main checks |
|---|---|---|
| Surveyor | `Site` | Parcel sets, geometry and expected refusals |
| Zoning | `ZoneFindings` | Zone codes, legend claims and ambiguity flags |
| Document | `DocNotes` | Expected statements, citations and forbidden claims |
| End-to-end | `VerifiedStudy` | Critical study facts, forbidden claims and envelope diagnostics |

`cases/` records item briefs; `datasets/` contains runnable expectations; `fixtures/`
retains source snapshots, calculations and review evidence. `gt/` contains independent
maintenance tools. Test-harness fixtures under `tests/` are synthetic and separate.

## 2. Run experiments

Install dependencies, configure credentials and run both ingestion steps as described in
the root README. Agent execution and geographic lookups require network access and may cost
money. From the repository root:

```sh
uv run python -m evals.run eval.dataset=surveyor eval.phoenix.enabled=false
uv run python -m evals.run eval.dataset=zoning eval.phoenix.enabled=false
uv run python -m evals.run eval.dataset=doc eval.phoenix.enabled=false
uv run python -m evals.run eval.dataset=e2e eval.phoenix.enabled=false
uv run python -m evals.run eval.dataset=all eval.phoenix.enabled=false
```

Select individual items with `eval.items=[s01_joliot_curie]`. The default status filter is
`[verified]`. Invalid or empty selections fail before graph/model execution.
Use `--cfg job` to inspect composed configuration without running an experiment.

`eval.max_cost_usd` stops launching work once the budget is reached; concurrently running
items may finish after that point. `eval.concurrency` controls local parallelism. Use distinct
`hydra.run.dir` overrides for processes started within the same second.

Phoenix is enabled by default. Start it with `uv run phoenix serve`, or disable it explicitly
as above. Disabling Phoenix does not disable tracing globally or make model execution offline.

## 3. Outputs and rescoring

Each run writes under `outputs/evals/<date>/<time>/`:

- `.hydra/`: composed configuration and CLI overrides.
- `records/`: delivered outputs, messages, failures, usage and rejected submissions per item.
- `scores.json`: per-item diagnostics and level summaries.
- `summary.md`: a readable summary, with logs alongside it.

To rescore matching saved records without executing the agents:

```sh
uv run python -m evals.run eval.dataset=all eval.phoenix.enabled=false eval.rescore=outputs/evals/2026-10-18/12-25-42
```

The selected datasets must match the records. Uncached assertions may still call the judge.
The compact handoff includes scores/configuration, not raw records; it supports inspecting
and regenerating the published presentation, not rerunning this rescore command by itself.

## 4. Scoring definitions

Key-value facts use exact/normalized comparisons, configured numeric tolerances, set
requirements or alternatives. Regulatory evidence requires valid citations matched to the
expected source. Statement/forbidden-claim assertions are judged by the configured model.
The judge is **uncalibrated**; there is no supported calibration command in this submission.

An ordinary item passes when every **critical grounded fact** passes and no `must_not`
claim is detected. Noncritical facts still contribute to accuracy. Missing ordinary output
fails. The deliberately unknown-address item instead requires completed geographic lookups,
an explained refusal, no parcel submission/artifact and no runtime error.

`must_flag` coverage, anti-pattern hits, citation diagnostics outside critical facts and
envelope recomputation are reported separately; they do not independently determine item
pass. A passing item is not certification of the whole output. Zoning has no regulatory
citation fields, so its grounded accuracy equals answer accuracy; the scorer does not verify
the meaning of a crop's pixels.

Envelope diagnostics separate disagreement with expected parameters from disagreement with
recomputation. The same production geometry code performs the consistency check, so it is
not an independent proof of the algorithm. Wholly prohibited programs have no envelope.

Level pass-rate intervals use Wilson intervals; fact accuracy uses bootstrap resampling
over items. A small single-run comparison does not establish causal effects or model
superiority. Agent costs use configured token prices and exclude judging costs; judge costs
are recorded separately. Reported per-item latency differs from total elapsed time when
items run concurrently.

## 5. Maintain expected answers

```sh
uv run python -m evals.gt.cases list surveyor
uv run python -m evals.gt.cases show surveyor s01_joliot_curie
uv run python -m evals.gt.check evals/datasets/surveyor/s01_joliot_curie.yaml
uv run python -m evals.gt.zones.audit
```

Use the page-verification helper's usage for checking quotes against the ingested corpus:
`uv run python -m evals.gt.pages`. Independent geographic settings live in
`conf/ground_truth/default.yaml`; registration metadata is retained beside zoning fixtures.
These tools do not call the agent under test to establish expected answers.

Regenerating geographic expectations requires the archived **91272_PLU_20210706** vector
layers in `data/gpu_2021/`, including SHP/SHX/DBF/PRJ companions. Original layer hashes and
oracle results are retained in fixture/provenance notes. The original download URL was not
recorded, so a fresh clone cannot automatically reproduce that acquisition. Obtain the exact
archive through the Geoportail de l'urbanisme archive and check its hashes before regeneration;
do not substitute current zoning. Retained snapshots can be inspected without downloading it.

Keep source fixtures and reviewer notes when editing a case. Validate schema, quote evidence
and independent geographic calculations before marking it verified. Generation prompts are
under `prompts/evals/generate/`; the actual review process and its limits are documented in
the dataset README.
