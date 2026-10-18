# Contributor guide

This repository builds a cited planning-regulation study from PDFs and geographic services.
Follow [CODING_STANDARDS.md](CODING_STANDARDS.md). [README.md](README.md) is the startup guide;
[evals/README.md](evals/README.md) defines scoring. Historical local files in ignored `docs/`
are not architectural authority.

## Current architecture

`agent.agents.config.load_config(overrides)` composes configuration for server, CLI and evals.
Hydra `_target_` nodes construct services and tools. Models are created only in `llm/`;
prompts are read through shared configuration helpers.

Dependencies flow from contracts to runtime, adapters, tools, agents, then entrypoints.
A module never imports a layer to its right. Runtime has no I/O or LangChain dependency.
Ingestion, model services and observability have their own responsibilities.

| Responsibility | Location under `src/agent/` |
|---|---|
| Validated shared schemas and artifacts | `contracts/` |
| Pure geometry, citations, reports, revisions | `runtime/` |
| HTTP, corpus files, page/image storage, georeference files | `adapters/` |
| PDF classification/splitting and raster registration | `ingest/` |
| Models, caching, cost and output limits | `llm/` |
| Thin model-facing tools and submission gates | `tools/<area>/` |
| Graph assembly and config loading | `agents/` |
| Logging/tracing | `observability/` |
| CLI, Agent Server graph and image routes | `entrypoints/` |

`conf/` owns settings/factory wiring; `prompts/` owns system instructions and playbooks.
`tests/` contains offline tests. `evals/` contains the harness, benchmark items, source
fixtures and independent ground-truth maintenance tools. `handoff/` contains final deliverables.

## Workflow and contracts

Read `prompts/playbooks/study.md`. Surveyor establishes `site`; zoning reads its parcels on
the georeferenced plan and delivers `zone`. Document tasks then deliver `notes.rules`,
`notes.oap`, `notes.destinations` and optional focused labels. Architect reads these artifacts
and delivers `envelope`. Orchestrator decides admissibility/ambiguities and submits `Study`;
the gate returns `VerifiedStudy`. A wholly prohibited program skips the architect and has
`envelope: null`; other programs require an envelope artifact containing only eligible
buildings, while admissibility retains the complete program.

The same specialist graph is delegated to by the orchestrator and called by component evals
(`build_subagent(cfg, name)`). Only document tasks run concurrently in the prescribed workflow.
Image pruning changes model requests, not stored messages.

Artifacts are validated JSON in `ArtifactsState.artifacts`. Read them with
`read_artifact(artifacts, key, Contract)`. `submit_tool(...)` builds a single tool;
`submit_tools(...)` builds submit/revise tools. Finalizers receive validated input and
artifacts, then return a stored model or raise `SubmissionRejected`. Rejections retain a
draft in tool-message metadata; revisions edit paths and rerun the same pipeline.
`build_tools` flattens factories returning either one tool or a list.

The gate checks artifact consistency, retained questions, citations and envelope inputs,
recomputes geometry, and saves evidence. Text checks do not verify legal interpretation;
raster crops are inspectable evidence, not automatically verified zoning. Acceptance does
not establish complete legal compliance. Area caps now trim physical footprints before
recomputing slices; the clipping is conservative, not a layout optimizer.

## Configuration and extension

`conf/config.yaml` selects case, corpus, models, agents, retrieval, geography, images and
policies. `conf/eval.yaml` adds evaluation settings. Default ingestion builds both the text
index and plan registration; README documents separate recovery commands.

Add tool factories in `tools/<area>/`, pure logic in runtime and external access in adapters.
Declare factories in the relevant agent's tools list:

```yaml
tools:
  - _target_: agent.tools.geo.geocode.geocode_tool
    geocoder: ${geo.geocoder}
    max_results: ${geo.max_results}
```

Add specialists through `conf/subagents/<name>.yaml` nested under the name, a Markdown prompt,
a model node and typed submit contract. Enable them in the config defaults.
Overrides work on CLI (`models.nodes.orchestrator.max_tokens=8000`) and per server run:

```json
{"configurable": {"overrides": ["models.nodes.orchestrator.max_tokens=8000"]}}
```

Treat global logging/tracing/image routing as startup settings. Per-run configuration does
not necessarily reconfigure process-global services.

## Development

```sh
uv sync --locked
uv run ruff format .
uv run ruff check .
uv run ty check
uv run pytest
```

All checks must pass. Use subagents when useful with clear shared-file ownership; the main
agent coordinates/reviews. Test changed invariants. Ordinary tests must not make paid calls.

```sh
uv run python -m agent.entrypoints.ingest
uv run python scripts/smoke_server.py --startup-only
uv run langgraph dev
uv run python -m agent.entrypoints.run
uv run python -m evals.run eval.dataset=surveyor eval.phoenix.enabled=false
```

Smoke uses port 2025 and stops its server; omitting `--startup-only` makes one paid call.
Disabling Phoenix does not make evals offline. The suite has 20 surveyor, 20 zoning,
20 document and 10 end-to-end items. Handoff results are frozen historical snapshots.

Dependencies: use `uv add <pkg>` / `uv add --dev <pkg>`; never edit `uv.lock` manually.
Declare direct imports directly. Secrets remain in `.env`, never in Git.

## Submission

Track maintained source, tests, source PDFs, benchmark evidence, README, this guide, standards
and `handoff/`. Ignore local `docs/`, `artifacts/`, `sites/`, `data/` and `outputs/`.
Do not add the nested authoring repository under `sites/` as a gitlink. Preserve font licenses
and source provenance. Rebuild historical report presentation with:

```sh
uv run python -m scripts.build_eval_report handoff
```
