# Regulatory buildability agent

An agent that reads French planning documents and produces a cited buildability study:
the applicable zone, permitted uses, regulatory limits, and a computed building envelope.
The reference case is **4 rue Joliot Curie, Gif-sur-Yvette**, for a student residence and a
residence for young workers in separate buildings.

## Explore the submission

- **[Reference parcel study](handoff/study/report.md):** read the complete, auditable regulatory
  study for 4 rue Joliot Curie (38 verified citations, computed 3D envelope, ambiguities and visual evidence).
- **[Workflow site](handoff/workflow/index.html):** follow ingestion, the four specialist
  agents, validation and delivery operation by operation. Includes a recorded app demo.
- **[Evaluation report](handoff/evaluation.html):** compare historical configurations on
  70 cases. [Scores, configurations and limitations](handoff/evaluation/README.md) explain
  the evidence behind the report.
- **The repository:** use the code map below; [CLAUDE.md](CLAUDE.md) describes the current
  architecture and [CODING_STANDARDS.md](CODING_STANDARDS.md) the contribution rules.

The report and study open directly. Serve the workflow site over HTTP because it fetches its data.
From the repository root, with Python installed:

```sh
python -m http.server 4173 --bind 127.0.0.1 --directory handoff
```

Open **http://localhost:4173/workflow/** or **http://localhost:4173/evaluation.html**.
Viewing these files needs no API key, ingestion or model calls. The workflow is an explanation
with saved illustrations; it does not run the backend.

## Install

Run commands from the repository root. Install **uv** first; it provisions Python 3.13 or
newer and the locked dependencies:

```sh
uv sync --locked
```

On first setup, copy the environment template and set `ANTHROPIC_API_KEY` in `.env`:

```powershell
# PowerShell
Copy-Item .env.example .env
```

```sh
# macOS / Linux
cp .env.example .env
```

Do not overwrite an existing `.env`. Existing environment variables take precedence.
The template disables tracing, so Phoenix is optional. Model calls incur API charges.

## Prepare the source documents

The three input PDFs are bundled under `ressources/`. Build both required local caches:

```sh
uv run python -m agent.entrypoints.ingest
```

This extracts/classifies PDFs, splits their text into sections, and georeferences the raster
zoning plan against the official commune outline fetched from IGN API Carto. It writes:

- `data/gif-sur-yvette@2021-07-06/corpus.json`: document pages and searchable sections.
- `data/gif-sur-yvette@2021-07-06/georef/plu_reglement_graphique.json`: fitted ground-to-plan
  transform, registration errors and source metadata.
- `outputs/georef/`: diagnostic mask and boundary overlay images.

The classifier requires the API key; georeferencing requires geographic-service access.
Caches are generated locally and excluded from Git. To rebuild only one step:

```sh
uv run python -m agent.entrypoints.ingest corpus
uv run python -m agent.entrypoints.ingest georef
```

Rebuild the corpus after changing PDFs or splitting settings. Rebuild the georeference after
changing the plan, rendering or fit settings. Registration is approximate; the zoning tool
reports uncertainty rather than treating the overlay as an exact legal boundary.

## Run

Check the real Agent Server and graph schema without a model call:

```sh
uv run python scripts/smoke_server.py --startup-only
```

This uses port 2025 and stops its server afterward. It does not verify ingested caches,
credentials or external services. Omit `--startup-only` to test one paid model response.

Run the reference study unattended:

```sh
uv run python -m agent.entrypoints.run
```

Known program facts come from `conf/case/reference.yaml`; the CLI disables clarification.
Hydra overrides change the address, program, models or policies. Inspect configuration
without running a study:

```sh
uv run python -m agent.entrypoints.run --cfg job
uv run python -m agent.entrypoints.run models.nodes.orchestrator.max_tokens=8000
```

Runs write `run_summary.json`, `final_message.md` and logs under `outputs/<date>/<time>/`.
An accepted study also writes `verified_study.json`, `report.md` and `evidence/` crops.
Exit code 1 means no study was accepted; inspect logs and submission errors.

For interactive use:

```sh
uv run langgraph dev
```

The Agent Server listens on **http://localhost:2024**, graph ID **agent**. The optional Next.js
client is in `ui/`; see [its setup instructions](ui/README.md). Backend and evals run
independently of the client. API and geographic services require internet access.

For tracing, start `uv run phoenix serve`, set `AGENT_TRACING=true` in `.env`, and restart
the server. Phoenix listens on port 6006. CLI tracing can also be disabled with
`policies.tracing.enabled=false`; evals have a separate `eval.phoenix.enabled` switch.

## Follow the code

The stack is LangGraph, deepagents, Anthropic models and Hydra. The workflow is defined in
[`study.md`](prompts/playbooks/study.md), assembly in
[`orchestrator.py`](src/agent/agents/orchestrator.py), and final validation in
[`gate.py`](src/agent/tools/study/gate.py).

1. **Surveyor:** selects cadastral parcels; code builds their union, area and edges.
2. **Zoning analyst:** reads labels/legend items around a georeferenced parcel outline.
3. **Document analyst:** extracts cited rules, OAP orientations and destination notes.
4. **Architect:** translates notes into envelope rules and a proposed building arrangement.
5. **Orchestrator:** resolves interpretations and submits a typed study.
6. **Gate:** checks consistency and quotes, recomputes geometry and saves evidence crops.

Site and zoning run sequentially; document tasks can run in parallel. Specialists deliver
typed artifacts into graph state. Rejections return errors; revision tools apply focused
edits. When every proposed use is prohibited, the gate accepts a cited negative study
without inventing an envelope. Mixed programs keep every admissibility verdict, but
compute geometry only for buildings whose uses are not prohibited.

```text
src/agent/
  contracts/       Shared validated inputs, findings and outputs
  runtime/         Pure geometry, citation matching, reports and revisions
  adapters/        HTTP, corpus files, georeferencing and image storage
  tools/           Model-facing wrappers and submission gates
  agents/          Configuration loading and graph assembly
  ingest/          PDF extraction, classification, splitting and plan registration
  llm/             Model creation, usage accounting and output limits
  observability/   Logging and Phoenix tracing
  entrypoints/     CLI, Agent Server and image routes
conf/              Hydra settings and factory wiring
prompts/           Agent instructions and playbooks
evals/             Benchmarks, scoring, source evidence and maintenance tools
tests/             Offline tests
ressources/        Source PDFs
handoff/           Workflow site, historical evaluation report, and reference study
```

## Checks and evaluations

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
```

Tests use fixtures/fakes. Some real-corpus tests require ingestion; the rest run without
credentials or network access. The benchmark has **20 surveyor, 20 zoning, 20 document,
and 10 end-to-end items**. Run a paid experiment without Phoenix:

```sh
uv run python -m evals.run eval.dataset=surveyor eval.phoenix.enabled=false
```

Disabling Phoenix does not make execution offline. See [evals/README.md](evals/README.md)
for selection, budgets, rescoring and scoring definitions, and the
[dataset provenance](evals/datasets/README.md) for expected-answer construction.
Handoff results are historical runs from 18 October 2026, before submission fixes; they
are not a benchmark of the final cleaned code. Rebuild their presentation without API calls:

```sh
uv run python -m scripts.build_eval_report handoff
```

## Limits and troubleshooting

Acceptance means the implemented checks passed. It does not certify planning permission,
ownership, complete legal applicability or raster interpretation. Quote matching checks
source text, not legal interpretation. Geometry uses a simplified arrangement and conservative
clipping for area caps; it does not design parking, calculate dwelling yield or prove a global
optimum. Storey caps are reported separately from volume. Standard study-topic minimums are
enforced from shared configuration; arbitrary focused labels and building-specific topic
completeness remain model-declared. Historical expected answers were model-worker reviewed,
without human sign-off; the judge is not calibrated.

- **Missing corpus/georeference:** run the corresponding ingest step above.
- **Authentication/model error:** check the key, credit and access to configured models.
- **Port conflict:** use `--port 2026` for the smoke script or `--port 2027` for `langgraph dev`.
- **Phoenix connection refused:** disable tracing or start Phoenix; check the separate eval switch.
- **Windows terminal encoding:** set `$env:PYTHONUTF8='1'` before launching commands.
- **Client integration:** wholly prohibited studies have `envelope: null`; clients must handle
  this negative-study outcome.
