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
uv run python -m agent.entrypoints.run models.nodes.orchestrator.effort=low   # any Hydra override
```

The CLI runs unattended (`ask_user` disabled; program facts come from `case.facts`). Each run
writes to its Hydra run dir `outputs/<date>/<time>/`: `verified_study.json` (the study accepted
by the `submit_study` gate), `report.md`, `run_summary.json` (cost per model, tokens, wall time,
headline results, citation pass rate) and `final_message.md`. A full run costs about $1–2.

### Chat with the agent (Agent Server + chat UI)

```bash
uv run langgraph dev                                         # Agent Server on http://localhost:2024
git clone https://github.com/langchain-ai/agent-chat-ui tools/agent-chat-ui   # first time only
cd tools/agent-chat-ui && pnpm install && pnpm dev           # UI on http://localhost:3000 (graph id: agent)
```

Ask for a study in the chat, e.g. *"Buildability study for 4 rue Joliot Curie, 91190
Gif-sur-Yvette: one Résidence Sociale Étudiante and one Résidence Jeunes Actifs in two separate
buildings."* The orchestrator loads the `study` playbook and delegates to its four sub-agents. In
the chat, `ask_user` is enabled: its questions appear as an interrupt card with one field per
question, pre-filled with the agent's recommendation (approve, edit, or reject with a free-text
reply). Per-run Hydra overrides go in the run config:
`{"configurable": {"overrides": ["models.nodes.orchestrator.effort=low"]}}`.

### Tracing (Phoenix)

```bash
uv run phoenix serve                                          # UI and collector on http://localhost:6006
uv run python -m agent.entrypoints.run policies.tracing.enabled=true
```

For the Agent Server, set `policies.tracing.enabled: true` in `conf/policies/default.yaml`
(tracing is set up once per process). Spans go to project `policies.tracing.project`.

## Repository layout

```
conf/        Hydra configuration groups
prompts/     system prompts, sub-agent prompts, playbooks (Markdown)
src/agent/   contracts · runtime · adapters · ingest · llm · tools · agents · observability · entrypoints
tests/       unit tests mirroring src/agent/
evals/       eval sets and scorers
ressources/  input planning documents (PDF)
docs/        design, coding standards, roadmap
tools/       external tools (agent-chat-ui)
```

## Documentation

- [Design](docs/DESIGN.md): architecture, inputs and outputs, sub-agents, evolution path
- [Coding standards](docs/CODING_STANDARDS.md)
- [v0 plan](docs/V0_PLAN.md): work packages and acceptance criteria
- [Roadmap](docs/ROADMAP.md): deferred decisions, post-v0 improvements, rejected options
- [CLAUDE.md](CLAUDE.md): where things go, and the dev workflow

## Status

v0 runs end to end: the reference case produces a gate-verified study and its report from the
CLI and from the chat UI. Orchestrator (deepagents) with four sub-agents (`site_locator`,
`zoning_map_reader`, `regulation_researcher`, `oap_analyst`), on-demand `study` playbook, hard
`submit_study` gate (schema, envelope geometry, verbatim citation check), `ask_user` interrupt,
Hydra CLI and Phoenix tracing. Next: the eval set, then iteration driven by eval failures.
