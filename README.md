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
cp .env.example .env          # set ANTHROPIC_API_KEY
uv run langgraph dev          # Agent Server on http://localhost:2024
git clone https://github.com/langchain-ai/agent-chat-ui tools/agent-chat-ui   # first time only
cd tools/agent-chat-ui && pnpm install && pnpm dev   # UI on http://localhost:3000
```

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

Scaffold only. The v0 end-to-end agent comes next, then the eval set, then iteration driven by eval failures.
