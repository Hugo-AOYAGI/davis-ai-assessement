# CLAUDE.md

Regulatory-analysis agent (LangGraph + deepagents, Hydra, Phoenix, Claude models) producing a
buildability study from planning documents. Read `docs/DESIGN.md` before changing architecture
and follow `docs/CODING_STANDARDS.md` for every change.

## Where things go

| You are adding… | Put it in |
|---|---|
| A Pydantic schema shared between modules (`Study`, `Citation`, sub-agent outputs) | `src/agent/contracts/` |
| Pure deterministic logic (geometry, citation matching), no LangChain, no I/O | `src/agent/runtime/` |
| Access to the outside world (HTTP APIs, corpus files on disk) | `src/agent/adapters/` (`geo/`, `corpus/`) |
| Document ingestion (classification, splitting, map storage) | `src/agent/ingest/` |
| Model creation, LLM caching, cost tracking | `src/agent/llm/` (the only place models are instantiated) |
| A LangChain tool exposed to an agent (thin wrapper over runtime/adapters) | `src/agent/tools/<area>/` |
| Orchestrator and sub-agent assembly from config | `src/agent/agents/` |
| Logging and Phoenix tracing setup | `src/agent/observability/` |
| A runnable entrypoint (Agent Server graph, Hydra CLI run, ingest CLI) | `src/agent/entrypoints/` |
| Any tunable value (model, temperature, path, threshold, limit) | `conf/<group>/` |
| A system prompt, sub-agent prompt or playbook | `prompts/{orchestrator,subagents,playbooks}/` |
| Eval sets, scorers, experiment runners | `evals/` |
| Unit tests | `tests/`, mirroring `src/agent/` |

Layering: `contracts ← runtime ← adapters ← tools ← agents ← entrypoints`. Never import to the right.

### Hydra config groups (`conf/`)

`case/` input address + program · `corpus/` corpus id and paths · `models/` per-node model
settings · `agent/` orchestrator + playbook · `subagents/` enabled sub-agents and their prompts ·
`retrieval/` navigation vs full sections, tool limits · `policies/` ask_user, citation check,
caching, tracing.

## Resources

| Resource | Location |
|---|---|
| Assessment brief | `Technical_assessment_AI_agents.pdf` |
| PLU regulatory text (465 p.; zone UMG p.320–332, lexique p.374–379) | `ressources/plu_reglement_91272_20210706.pdf` |
| PLU zoning plan (single raster A0 image) | `ressources/plu_reglement_graphique_91272_20210706.pdf` |
| OAP (Joliot Curie ch. 8, p.33–36) | `ressources/oap_91272_20210706.pdf` |
| Design decisions | `docs/DESIGN.md` |
| Coding standards | `docs/CODING_STANDARDS.md` |
| v0 work packages, file ownership, acceptance criteria | `docs/V0_PLAN.md` |
| Deferred decisions, post-v0 improvements, rejected options | `docs/ROADMAP.md` |
| Chat UI (external clone, gitignored: `git clone https://github.com/langchain-ai/agent-chat-ui tools/agent-chat-ui`) | `tools/agent-chat-ui/` |
| Ingested corpus cache, run outputs (gitignored) | `data/`, `outputs/` |

## Dev workflow

```bash
uv sync                      # install / update environment
uv run ruff format .         # format
uv run ruff check .          # lint (add --fix for autofixes)
uv run ty check              # type check
uv run pytest                # unit tests
```

All four must pass before a change is done. Use sub-agents whenever possible to write code and
run these checks; the main thread coordinates and reviews.

Running the agent:

```bash
uv run langgraph dev                         # Agent Server on http://localhost:2024 (graph: src/agent/entrypoints/graph.py)
cd tools/agent-chat-ui && pnpm install && pnpm dev   # chat UI on http://localhost:3000
```

Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`; never edit `uv.lock` by hand.
Secrets live in `.env` (`ANTHROPIC_API_KEY`), never committed.
