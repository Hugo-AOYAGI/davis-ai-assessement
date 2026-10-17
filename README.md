# Regulatory buildability agent

An AI agent that navigates French planning documents (PLU regulatory text, zoning plan, OAP) and
produces an auditable buildability study for a parcel: applicable zone and overlays, program
admissibility, envelope rules, the resulting buildable envelope, ambiguities, and a verified
citation for every conclusion.

Reference case: **4 rue Joliot Curie, 91190 Gif-sur-Yvette**, with one Résidence Sociale
Étudiante and one Résidence Jeunes Actifs in two separate buildings. The agent itself is
generic: address, program and document corpus are inputs.

## Stack

- **Agent**: LangGraph + deepagents (orchestrator, sub-agents, playbooks), Claude models
- **Configuration**: Hydra — every model, prompt, threshold and policy is configurable
- **Observability and evals**: Arize Phoenix + deterministic scorers
- **UI**: LangGraph Agent Server + agent-chat-ui
- **Tooling**: uv, ruff, ty, pytest

## Quick start

```bash
uv sync
cp .env.example .env                          # set ANTHROPIC_API_KEY
uv run python -m agent.entrypoints.ingest     # once: builds the corpus cache under data/
```

### Run a study from the command line

```bash
uv run python -m agent.entrypoints.run                       # reference case (conf/case/reference.yaml)
uv run python -m agent.entrypoints.run models.nodes.orchestrator.max_tokens=8000   # any Hydra override
```

The CLI runs unattended (`ask_user` disabled; program facts come from `case.facts`). Each run
writes to its Hydra run dir `outputs/<date>/<time>/`:

- `run_summary.json`: cost per model and per model node (orchestrator, each sub-agent),
  tokens, wall time, rejected submissions, headline results, citation pass rate;
- `final_message.md`: the orchestrator's last reply;
- `agent.log`: the run's log lines;
- when the gate accepted a study: `verified_study.json` (the study, site, labelled limits, zone,
  envelope, citation checks), `report.md`, and `evidence/` with the evidence crops the report
  links to (zoning-plan region and diagram views, saved by the gate under `data/crops/`).

The command exits with code 1 when no study was accepted.

### Chat with the agent (Agent Server + chat UI)

```bash
uv run langgraph dev                                         # Agent Server on http://localhost:2024
cd ui && pnpm install && pnpm dev                            # UI on http://localhost:3000 (graph id: agent)
```

Ask for a study in the chat, e.g. *"Buildability study for 4 rue Joliot Curie, 91190
Gif-sur-Yvette: one Résidence Sociale Étudiante and one Résidence Jeunes Actifs in two separate
buildings."* The orchestrator loads the `study` playbook and delegates to its three sub-agents. In
the chat, `ask_user` is enabled: its questions appear as an interrupt card with one field per
question, pre-filled with the agent's recommendation (approve, edit, or reject with a free-text
reply). Per-run Hydra overrides go in the run config:
`{"configurable": {"overrides": ["models.nodes.orchestrator.max_tokens=8000"]}}`.

### Tracing (Phoenix)

```bash
uv run phoenix serve                                          # UI and collector on http://localhost:6006
```

Tracing is on by default, for CLI runs and the Agent Server alike: start Phoenix first. Spans go to
project `policies.tracing.project`. Turn it off with `AGENT_TRACING=false` (the test suite does),
or with `policies.tracing.enabled=false` on a CLI run. The Agent Server reads it once at startup.

## How it works

The orchestrator plays the project lead: it loads a playbook (`load_playbook`), delegates with
`task`, reads the sub-agents' typed outputs (`read_artifact`), decides (destinations, verdicts,
limits, ambiguities), asks the user when allowed (`ask_user`) and submits the study to the
`submit_study` gate. Each sub-agent ends with a submit tool that validates its output and stores it
as an artifact in the graph state:

| Sub-agent | Job | Tools | Artifact |
|---|---|---|---|
| `surveyor` | address → parcels chosen → site (polygon, area, neutral edges) | `geocode`, `find_parcels`, `describe_parcels`, `site_view`, `submit_parcel` | `site` |
| `zoning_analyst` | finds the site on the raster zoning plan by eye; zone and legend items | `list_documents`, `site_view`, `view_image`, `zoom`, `submit_zone` | `zone` |
| `doc_analyst` | reads documents for an aim (rules, OAP, a chat question) and returns cited notes and open points; extracts, does not decide | `list_documents`, `list_sections`, `read_section`, `search`, `read_pages`, `view_image`, `zoom`, `site_view`, `submit_notes` | `notes.<label>` |

The study playbook runs `surveyor`, then `zoning_analyst`, then `doc_analyst` twice in parallel
(`rules` and `oap`). `submit_study` is plain code: it validates the `Study`, checks every quote on
its page, requires an ambiguity for every open point, labels the site limits (road / side / rear),
computes the envelope, saves the evidence crops, and returns the envelope figures on acceptance
(artifact `study`).

## Repository layout

```
conf/        Hydra configuration groups
prompts/     system prompts, sub-agent prompts, playbooks (Markdown)
src/agent/   contracts · runtime · adapters · ingest · llm · tools · agents · observability · entrypoints
tests/       unit tests mirroring src/agent/
evals/       eval sets and scorers
ressources/  input planning documents (PDF)
docs/        design, v1 refinements, coding standards, plans, roadmap
ui/          chat UI (Next.js, adapted from agent-chat-ui)
```

## Documentation

- [Design](docs/DESIGN.md): architecture, inputs and outputs, sub-agents, evolution path
- [Refinements](docs/REFINE.md): v1 decisions, brick by brick (wins where it differs from Design)
- [Coding standards](docs/CODING_STANDARDS.md)
- [v0 plan](docs/V0_PLAN.md): work packages and acceptance criteria
- [v1 plan](docs/V1_PLAN.md): v1 seams, work packages, as-built deviations
- [Roadmap](docs/ROADMAP.md): deferred decisions, post-v0 improvements, rejected options
- [CLAUDE.md](CLAUDE.md): where things go, and the dev workflow

## Status

v1 (the [REFINE](docs/REFINE.md) refactor of the working v0): orchestrator (deepagents) with three
sub-agents (`surveyor`, `zoning_analyst`, `doc_analyst`), on-demand `study` playbook, hard
`submit_study` gate (schema, verbatim citation check, open points ↔ ambiguities, edge labelling,
envelope with green cap, evidence crops), `ask_user` interrupt, Hydra CLI and Phoenix tracing.
v0 baseline reference run: accepted at the first submission, 46/46 text-verifiable citations
verified, 5 ambiguities, $0.71. Next: rerun the reference case against that baseline, then the
eval set and iteration driven by eval failures.
