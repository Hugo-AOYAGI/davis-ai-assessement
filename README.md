# Regulatory buildability agent

An AI agent that reads French planning documents and produces a cited buildability study:
which zone applies, whether the proposed uses are permitted, the applicable limits, and a
computed building envelope. The reference case is **4 rue Joliot Curie, Gif-sur-Yvette**:
a student residence and a residence for young workers in two separate buildings.

The backend uses LangGraph, deepagents, Anthropic models and Hydra configuration. It separates
model judgement from deterministic geometry, quote verification and submission validation.
The included Next.js chat client connects to the LangGraph Agent Server.

## Start here

Run commands from the repository root unless a step says otherwise. Install **uv** first;
`uv sync --locked` provisions the Python version required by `pyproject.toml` (3.13 or newer)
and the locked dependencies. Model calls require an Anthropic API key and incur API charges.

```sh
uv sync --locked
```

Copy the environment template, then edit `.env` to set `ANTHROPIC_API_KEY`:

```powershell
# PowerShell
Copy-Item .env.example .env
```

```sh
# macOS / Linux
cp .env.example .env
```

The template disables tracing, so Phoenix is optional. Existing environment variables take
precedence over `.env`; copying the template overwrites an existing file, so do this only on
first setup.

Build the corpus from the three bundled PDFs (calls the document classifier):

```sh
uv run python -m agent.entrypoints.ingest
```

This writes `data/gif-sur-yvette@2021-07-06/corpus.json`. Re-run ingestion after changing the
PDFs or splitter configuration. The cache is local and is not included in a fresh clone.

Check that the real Agent Server starts and exposes the graph schema, without a model call:

```sh
uv run python scripts/smoke_server.py --startup-only
```

The check uses port **2025**, logs its server output to a temporary file, and stops its server
when finished. To also test credentials and one short model response, omit `--startup-only`.
That check calls the real API.

## Run a study

```sh
uv run python -m agent.entrypoints.run
```

The CLI runs unattended: clarification tools are disabled, and known program facts come from
`case.facts` in `conf/case/reference.yaml`. Address, program, corpus, models and policies can be
changed through Hydra overrides:

```sh
uv run python -m agent.entrypoints.run models.nodes.orchestrator.max_tokens=8000
uv run python -m agent.entrypoints.run --cfg job
```

`--cfg job` prints configuration without running a study. A study run writes to
`outputs/<date>/<time>/`:

- `run_summary.json`: acceptance, headline findings, tokens, configured cost estimates and timing.
- `final_message.md` and `agent.log`: the final response and application logs.
- On acceptance: `verified_study.json`, `report.md`, and `evidence/` with linked image crops.

Exit code **1** means no study was accepted. Inspect the log and rejected submission messages.
API access and geographic services require an internet connection; a successful startup check
does not verify those external dependencies.

## Run the server

```sh
uv run langgraph dev
```

The Agent Server listens on **http://localhost:2024**, with graph ID **agent**. It supports
interactive clarification and accepts Hydra overrides in each run's configuration:

```json
{"configurable": {"overrides": ["models.nodes.orchestrator.max_tokens=8000"]}}
```

The optional chat client is in `ui/`; see its own setup instructions. The backend can be run
and evaluated independently of the client.

For Phoenix tracing, run `uv run phoenix serve` in another terminal, set
`AGENT_TRACING=true` in `.env`, and restart the agent server. Phoenix listens on
**http://localhost:6006**. CLI tracing can also be disabled with
`policies.tracing.enabled=false`.

## Follow the code

Start with `prompts/playbooks/study.md` for the workflow, then
`src/agent/agents/orchestrator.py` for assembly and `src/agent/tools/study/gate.py` for acceptance.

1. **Surveyor** chooses cadastral parcels; code builds the site geometry and neutral edges.
2. **Zoning analyst** reads the raster zoning plan and records zone and legend findings.
3. **Document analyst** extracts cited notes for the rules and OAP planning orientations.
4. **Orchestrator** decides uses, limits and ambiguities, then submits a typed `Study`.
5. **Submission gate** validates inputs, checks quotes against PDF text, requires open points to
   be addressed, labels boundaries, computes the envelope and stores evidence crops.

Sub-agents submit typed artifacts (`site`, `zone`, `notes.<label>`) into graph state. The gate
produces `VerifiedStudy`, the shared output used by the report and end-to-end scorers.
Failed submissions return errors for the model to correct; revision tools apply focused edits.

The envelope is currently a **single prism**, capped by setbacks, footprint and green-space
ratios and maximum height. It does not establish that two buildings fit, calculate parking
capacity, or model stepped heights. Raster evidence is preserved for inspection but is not
verified against text. An accepted study is an output that passed these implemented checks.

```text
src/agent/
  contracts/       Shared Pydantic inputs, findings and study outputs
  runtime/         Pure geometry, citation matching, report rendering and revisions
  adapters/        HTTP services, corpus files and page/image storage
  tools/           Tools and submission gates exposed to the models
  agents/          Configuration loading and graph assembly
  ingest/          PDF extraction, classification and section splitting
  llm/             Model creation, usage accounting and output limits
  observability/   Logging and Phoenix tracing
  entrypoints/     CLI ingestion/studies, server graph and image routes
conf/              Hydra settings and tool factory wiring
prompts/           Model instructions and playbooks
evals/             Evaluation harness and shipped dataset
tests/             Offline tests, largely mirroring the backend
ressources/        Bundled source PDFs
docs/              Design decisions, review and evaluation documentation
```

Configuration supplies factories with `_target_` entries; tool wrappers call adapters and pure
runtime logic. Start with `conf/config.yaml`, then the relevant configuration group.

## Checks and evaluations

```sh
uv run ruff check src evals scripts tests
uv run ruff format --check src evals scripts tests
uv run ty check
uv run pytest
```

Tests use fixtures and fakes. Real-corpus acceptance tests are skipped until ingestion has run.
Coding conventions and file/folder limits are in [CODING_STANDARDS.md](docs/CODING_STANDARDS.md).

The eval harness supports surveyor, zoning, document and end-to-end tasks, but the repository
currently ships **one verified surveyor item**. The broader 70-item suite is a plan, not a
completed benchmark. Run the included item without Phoenix:

```sh
uv run python -m evals.run eval.dataset=surveyor eval.phoenix.enabled=false
```

This still calls the real agent and geographic services. Disabling Phoenix does not make model
execution offline. To rescore saved records, add
`eval.rescore=outputs/evals/<date>/<time>` with a matching dataset selection; scoring may call
the judge when uncached judgement is needed. Outputs include `records/`, `scores.json` and
`summary.md`. See [EVALS.md](docs/EVALS.md) for scoring and dataset status.

## Troubleshooting

- **No ingested corpus:** run the ingest command before studies or evals.
- **Authentication or model errors:** check `.env`, API credit and model access. Model IDs and
  local pricing estimates are configured in `conf/models/default.yaml`.
- **Connection refused on port 6006:** disable tracing, or start Phoenix. Evals have a separate
  `eval.phoenix.enabled` switch.
- **Port in use:** pass `--port 2026` to the smoke check, or `--port 2027` to `langgraph dev`.
- **Windows terminal encoding errors:** set `$env:PYTHONUTF8='1'` before launching the command.

## Further reading

- [Code review](docs/CODE_REVIEW.md): findings, fixes, field usage and remaining work.
- [Design](docs/DESIGN.md) and [v1 refinements](docs/REFINE.md): design history; refinements
  supersede the original design where they differ.
- [Round 2 proposal](docs/REFINE_v2.md): unimplemented envelope and architect design.
- [Roadmap](docs/ROADMAP.md): deferred improvements.
- [CLAUDE.md](CLAUDE.md): contributor map and extension instructions.

The historical plans in `docs/V0_PLAN.md` and `docs/V1_PLAN.md` explain implementation stages;
they are not the startup guide or a statement of current benchmark results.
