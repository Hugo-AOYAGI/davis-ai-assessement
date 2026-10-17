# CLAUDE.md

Regulatory-analysis agent (LangGraph + deepagents, Hydra, Phoenix, Claude models) producing a
buildability study from planning documents. Read `docs/DESIGN.md` and `docs/REFINE.md` (which
wins where they differ) before changing architecture, and follow `docs/CODING_STANDARDS.md` for
every change.

## Where things go

| You are adding… | Put it in |
|---|---|
| A Pydantic schema shared between modules (`Study`, `Citation`, sub-agent outputs) | `src/agent/contracts/` |
| Pure deterministic logic (geometry, citation matching), no LangChain, no I/O | `src/agent/runtime/` |
| Access to the outside world (HTTP APIs, corpus files and page images on disk) | `src/agent/adapters/` (`geo/`, `corpus/`, `images/`) |
| Document ingestion (classification, splitting) | `src/agent/ingest/` |
| Model creation, LLM caching, cost tracking | `src/agent/llm/` (the only place models are instantiated) |
| A LangChain tool exposed to an agent (thin wrapper over runtime/adapters) | `src/agent/tools/<area>/` |
| Orchestrator and sub-agent assembly from config | `src/agent/agents/` |
| Logging and Phoenix tracing setup | `src/agent/observability/` |
| A runnable entrypoint (Agent Server graph, Hydra CLI run, ingest CLI) | `src/agent/entrypoints/` |
| Any tunable value (model, temperature, path, threshold, limit) | `conf/<group>/` |
| A system prompt, sub-agent prompt or playbook | `prompts/{orchestrator,subagents,playbooks}/` |
| Eval sets, scorers, experiment runners | `evals/` |
| Unit tests | `tests/`, mirroring `src/agent/` |
| Chat UI components (tool calls, sub-agents, ask_user, study view) | `ui/src/` |

Layering: `contracts ← runtime ← adapters ← tools ← agents ← entrypoints`. Never import to the right.

### Hydra config groups (`conf/`)

`case/` input address + program · `corpus/` corpus id and paths · `models/` per-node model
settings · `agent/` orchestrator + playbook · `subagents/` enabled sub-agents and their prompts ·
`retrieval/` navigation vs full sections, tool limits · `geo/` geographic services, site geometry
knobs, the shared `site_view` tool node · `images/` corpus page images (render dpi, image sizes)
and the tool image store · `policies/` ask_user, citation check, required notes, evidence crops,
tracing.

## Resources

| Resource | Location |
|---|---|
| Assessment brief | `Technical_assessment_AI_agents.pdf` |
| PLU regulatory text (465 p.; zone UMG p.320–332, lexique p.374–379) | `ressources/plu_reglement_91272_20210706.pdf` |
| PLU zoning plan (single raster A0 image) | `ressources/plu_reglement_graphique_91272_20210706.pdf` |
| OAP (Joliot Curie ch. 8, p.33–36) | `ressources/oap_91272_20210706.pdf` |
| Design decisions | `docs/DESIGN.md` |
| v1 decisions (supersede DESIGN where they differ) | `docs/REFINE.md` |
| v1 seams, work packages, as-built deviations | `docs/V1_PLAN.md` |
| Coding standards | `docs/CODING_STANDARDS.md` |
| v0 work packages, file ownership, acceptance criteria | `docs/V0_PLAN.md` |
| Deferred decisions, post-v0 improvements, rejected options | `docs/ROADMAP.md` |
| Chat UI (Next.js, adapted from langchain-ai/agent-chat-ui) | `ui/` |
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
cd ui && pnpm install && pnpm dev                     # chat UI on http://localhost:3000
```

Smoke checks: `uv run pytest tests/entrypoints` (offline graph build) and
`uv run python scripts/smoke_server.py` (starts `langgraph dev` on port 2025, sends one cheap
message, ~$0.01).

## How to extend

Everything is assembled from the composed config (`agent.agents.config.load_config(overrides)`,
the single loader for server, CLI and evals). Never build models, read prompts or hardcode
values elsewhere.

**Add a config knob**: put the value in the right `conf/<group>/` file, read it from the `cfg`
passed down to you, and pass it to your factory as an argument. Override it on the CLI
(`group.key=value`) or per run on the server:
`{"configurable": {"overrides": ["models.nodes.orchestrator.max_tokens=8000"]}}`.

**Add a tool**: write a factory function in `src/agent/tools/<area>/` that takes its knobs as
arguments and returns a `BaseTool`. Keep it thin (logic in `runtime/` or `adapters/`); its
description is what the model reads. Declare it in the `tools` list of the agent or sub-agent
that uses it:

```yaml
tools:
  - _target_: agent.tools.geo.geocode.geocode_tool   # factory, called by hydra.utils.instantiate
    geocoder: ${geo.geocoder}                        # knobs and clients as arguments
    max_results: ${geo.max_results}
```

**Add a sub-agent**: one file `conf/subagents/<name>.yaml`, content nested under `<name>:` (Hydra
merges all selected files into `subagents`), plus its prompt `prompts/subagents/<name>.md` and a
model node `models.nodes.<name>`. It must end by calling its submit tool:

```yaml
surveyor:
  description: Turns the case address into the site under study...  # read by the orchestrator
  prompt: prompts/subagents/surveyor.md
  model: surveyor                # key in models.nodes
  tools:
    - _target_: agent.tools.geo.geocode.geocode_tool
      geocoder: ${geo.geocoder}
      max_results: ${geo.max_results}
    - ${geo.site_view}           # shared ready-made tool node
    - _target_: agent.tools.submit.factory.submit_tool
      name: submit_parcel        # tool name
      artifact: site             # state key
      contract: {_target_: hydra.utils.get_class, path: agent.contracts.findings.site.ParcelChoice}
      finalize:                  # ParcelChoice -> Site (built by code)
        _target_: agent.tools.geo.site.parcel_finalizer
        surveyor: ${geo.surveyor}
      summarize: {_target_: hydra.utils.get_method, path: agent.tools.geo.site.summarize_site}
```

Enable it with `subagents=[surveyor,...]` (default: `surveyor`, `zoning_analyst`, `doc_analyst`
in `conf/config.yaml`).
`build_subagent(cfg, name)` returns the standalone graph; the orchestrator delegates to that same
graph, and evals invoke it with `{"messages": [HumanMessage(task)]}`.

**Artifacts and submit tools**: the graph state has an `artifacts` mapping (`ArtifactsMiddleware`
in `tools/submit/artifacts.py`). `submit_tool(*, name, artifact, contract, finalize=None,
summarize=None)` builds the tool `name`; it validates the model's arguments against the contract,
returns `field.path: message` errors to the model, and stores the result as JSON under
`artifacts[artifact]`. `artifact` may hold `{field}` placeholders filled from the submission's
top-level fields (`notes.{label}` gives `notes.rules`, `notes.oap`); `summarize(stored) -> str` is
appended to the `<key> accepted.` reply. Artifacts written by a sub-agent reach the
orchestrator's state. Read one back with `read_artifact(state["artifacts"], key, Contract)`. A
gate such as `submit_study` passes `finalize(submission, artifacts) -> stored` and raises
`SubmissionRejected(errors)` to refuse.

Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`; never edit `uv.lock` by hand.
Secrets live in `.env` (`ANTHROPIC_API_KEY`), never committed.
