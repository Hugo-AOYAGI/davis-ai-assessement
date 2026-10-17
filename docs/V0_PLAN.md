# v0 plan

Work packages (WP) to reach a working v0: the reference case runs end to end, through the CLI and
the chat UI, and returns a `VerifiedStudy` plus a Markdown report. Scope is
[DESIGN.md](DESIGN.md); anything not listed here is in [ROADMAP.md](ROADMAP.md) and out of v0.

## Order

```
WP0 Foundations
   ├── WP1 Ingestion ──── WP4 Regulation + OAP ──┐
   ├── WP2 Site ─────────────────────────────────┤
   ├── WP3 Map (spike first) ────────────────────┼── WP6 Integration
   └── WP5 Deterministic core ───────────────────┘
```

WP0 lands first. WP1, WP2, WP3 and WP5 then run in parallel. WP4 starts once WP1 is merged.
WP6 starts once everything else is merged.

## Rules for every WP

- **Delegate to sub-agents**: use sub-agents whenever possible to write code, run ruff / ty /
  pytest, and explore library source. The thread itself coordinates, reviews and decides; parallel
  sub-agents for independent modules.
- **Read first**: `CLAUDE.md`, `docs/DESIGN.md`, `docs/CODING_STANDARDS.md`, this file, and the
  code merged so far (WP0 sets the patterns for config, models, tools, sub-agents).
- **Workspace**: you run in your own git worktree on your own branch. Run `uv sync` first. Secrets
  and the ingested corpus are gitignored: copy `.env` from the main checkout
  (`C:\Users\aoyag\Desktop\Davis AI Assessment\.env`); build the corpus with the ingest entrypoint
  once WP1 is merged.
- **Stay in your lane**: only touch the files your WP owns (table below). Shared files
  (`conf/config.yaml`, `pyproject.toml`, `uv.lock`, `docs/`, `CLAUDE.md`) are WP0/WP6 territory.
  All v0 dependencies are already installed; if one is truly missing, add it and say so.
- **Contracts** (`src/agent/contracts/`) are the shared seams. Do not change them unless blocked;
  if you must, make the smallest additive change, update `tests/contracts/`, and report it.
- **No hidden API calls in tests**: pytest never hits the network or an LLM. HTTP is replayed
  from recorded fixtures under `tests/**/fixtures/`.
- **Budget**: the whole project has ~$250 of API credit. Keep live LLM runs few and small, and
  log their cost.
- **Library APIs**: deepagents, LangGraph and langchain-anthropic move fast. Read the installed
  source in `.venv` rather than relying on memory.
- **Done** means: the WP acceptance criteria pass, plus `uv run ruff format .`,
  `uv run ruff check .`, `uv run ty check`, `uv run pytest` all clean. Then commit on your branch
  (do not merge) and end with a short report: what was built, how to run it, deviations from this
  plan, contract changes, open issues.

## File ownership

| WP | Owns |
|---|---|
| WP0 | `conf/config.yaml`, `conf/{models,agent,case,policies}/`, `src/agent/{llm,observability,agents}/`, `src/agent/entrypoints/graph.py`, `src/agent/tools/submit/`, `prompts/orchestrator/`, `scripts/`, `CLAUDE.md` |
| WP1 | `src/agent/ingest/`, `src/agent/adapters/corpus/`, `src/agent/entrypoints/ingest.py`, `conf/corpus/` |
| WP2 | `src/agent/adapters/geo/`, `src/agent/runtime/geometry/` (site part), `src/agent/tools/geo/`, `prompts/subagents/site_locator.md`, its sub-agent config |
| WP3 | `src/agent/tools/` map module, `prompts/subagents/zoning_map_reader.md`, its sub-agent config, map-related corpus config |
| WP4 | `src/agent/tools/regulation/`, `conf/retrieval/`, `prompts/subagents/{regulation_researcher,oap_analyst}.md`, their sub-agent configs |
| WP5 | `src/agent/runtime/` (envelope, citations, report), `src/agent/tools/envelope/`, the `submit_study` gate |
| WP6 | `prompts/playbooks/`, `src/agent/tools/interaction/`, `src/agent/entrypoints/run.py`, enabled sub-agent list, Phoenix wiring, `README.md` |

Tests for each module go in the matching `tests/` folder and belong to the same WP.

---

## WP0 Foundations

**Goal**: a bare orchestrator served by `langgraph dev`, built entirely from Hydra config, with the
patterns every later WP copies.

- **Config loading**: Hydra Compose API (`initialize_config_dir` + `compose`), paths resolved
  from the project root, overrides accepted as a list. No `@hydra.main` on the server path.
- **Config groups** with a default file each: `models` (one entry per node: orchestrator,
  site_locator, zoning_map_reader, regulation_researcher, oap_analyst, ingest_classifier;
  Sonnet for agents, Haiku for ingestion), `agent`, `case` (the reference case), `policies`
  (`ask_user` mode, citation policy, tracing). Leave `corpus`, `retrieval`, `subagents` for their
  owners, with one placeholder each so the defaults list is final.
- **`llm/`**: the only place models are built (`_target_` + `instantiate`), with token/cost
  logging.
- **`observability/`**: logger setup.
- **`agents/`**: `build(cfg)` assembles the deepagents orchestrator from config: model, prompt
  file, tools, sub-agents. Define how a sub-agent is declared (one config file per sub-agent:
  name, description, prompt file, model key, tools as `_target_`), so WP2–WP4 each add their own
  file without editing a shared one. A sub-agent must also be buildable standalone (needed for
  per-sub-agent evals).
- **Graph state and submit pattern**: a state with an `artifacts` mapping, and a generic factory
  that turns a contract into a `submit_<artifact>` tool: validates with Pydantic, returns
  validation errors to the model, stores the artifact in state. Sub-agent artifacts must reach the
  parent graph state (needed by the `submit_study` gate, which reads `SiteContext` from state).
- **`entrypoints/graph.py`**: a short factory calling `build(cfg)`, honouring per-run overrides
  from `configurable` if the server calls the factory per run (verify), loading `.env` once.
- **Smoke tests**: a pytest test that builds the graph with a dummy key and no network; a
  `scripts/` check that starts `langgraph dev`, waits for health, and runs one cheap message.
- **Docs**: in `CLAUDE.md`, a short "how to add a tool / sub-agent / config knob" section.

**Done when**: `uv run langgraph dev` serves the graph, the chat UI (`tools/agent-chat-ui`) chats
with the bare orchestrator, and both smoke checks pass.

## WP1 Ingestion

**Goal**: `ingest` turns the three PDFs into a `Corpus` cached under `data/<corpus_id>/`.

- Per-page text (PyMuPDF), page images for raster pages.
- Document classification with the `ingest_classifier` model into `DocumentKind`.
- Heading splitter for `regulatory_text` (titre → zone → article) and `oap` (chapters), page
  ranges kept, repealed articles handled.
- `adapters/corpus/`: save/load a `Corpus`, lookups (section by zone/article, pages by range,
  definitions in the lexique), BM25 index over sections.
- `conf/corpus/`: corpus id, PDF paths, output dir, splitter patterns.

**Done when**: running the ingest entrypoint produces a corpus where zone UMG has articles 1–16 on
the right pages (p.320–332), the lexique and Titre I general provisions are sections, and the OAP
chapter 8 (p.33–36) is a section. Unit tests cover the splitter on extracted text fixtures.

## WP2 Site

**Goal**: `site_locator` turns an address into a `SiteContext`.

- `adapters/geo/`: address geocoder (BAN / Géoplateforme) and cadastre parcels (API Carto),
  endpoints in config, responses cached on disk, tests on recorded fixtures.
- `runtime/geometry/`: projection to a metric CRS (from config), parcel union, boundary
  classification: edges shared with a neighbour parcel are separating limits, others face the
  road; separating edges touching a road edge are `side`, the rest `rear`.
- `tools/geo/`: thin tools over the above; `site_locator` prompt, config, `submit_site`.

**Done when**: the reference address yields a valid `SiteContext` (parcel ids, area, typed
boundaries, geometric citations) in a live run, and geometry/adapters are unit-tested offline.

## WP3 Map

**Goal**: `zoning_map_reader` reads zone and overlays for the site from the raster zoning plan.

1. **Spike first**: find a reliable way to locate the site on the A0 image (it has no coordinates,
   street names or parcel numbers). Candidates: georeferencing the image once with control points
   stored in corpus config, then cropping around the projected parcel; or vision-guided search
   over tiles using landmarks. Write the findings as a short note in your report before building.
2. Build the chosen approach: crop/zoom tools, legend access, the sub-agent prompt and config,
   `submit_map_findings`.

**Done when**: a live run on the reference site returns `MapFindings` with zone `UMG`, the overlays
checked, and citations to the plan (legend item, crop).

## WP4 Regulation + OAP (after WP1)

**Goal**: `regulation_researcher` and `oap_analyst` produce `RegulationFindings` and
`OAPFindings` from the corpus.

- `tools/regulation/`: `list_sections`, `read_article(zone, n)`, `get_definition(term)`, BM25
  `search`, `read_pages(doc, from, to)`; both retrieval modes (`navigation`, `full_sections`) as
  `conf/retrieval/` variants.
- Prompts and configs for both sub-agents, `submit_regulation_findings`, `submit_oap_findings`.
- `regulation_researcher` also classifies the program into destinations (admissibility) and
  extracts envelope parameters and parking rules; ambiguities recorded, never resolved silently.

**Done when**: a live run on the reference case returns findings matching the corpus facts (UMG
height 20 m / R+5 for housing, parking 1 space per 150 m² for student residences, 20 % green
space, OAP Joliot Curie applicable), with verbatim citations.

## WP5 Deterministic core

**Goal**: the pure code behind the gate, fully unit-tested.

- `runtime/geometry/` (envelope part): prism envelope from `SiteContext` + `EnvelopeParameters`:
  each boundary edge buffered by its setback and removed from the site polygon, footprint ratio
  cap, green area, volume. Tolerances from config.
- `runtime/citations/`: quote normalisation (Unicode, case, whitespace, hyphenation, ligatures,
  quotes), fuzzy match on the cited page and its neighbours, `CitationCheck` results; threshold
  from config. Geometric citations are not checked against the corpus.
- `runtime/report/`: Markdown report rendered from a `VerifiedStudy`.
- `tools/envelope/`: `compute_envelope` tool. `submit_study` gate (using WP0's submit pattern):
  validate `Study`, read `SiteContext` from state, compute the envelope, check every citation,
  apply the citation policy (reject with errors returned to the model, or flag), store the
  `VerifiedStudy`.

**Done when**: unit tests cover the envelope on fixture parcels (rectangle, L-shape, setbacks
consuming the whole parcel), citation checks on real page text (exact, hyphenated, wrong page,
fabricated), and the gate's accept/reject paths.

## WP6 Integration

**Goal**: the full study works end to end.

- Study playbook (`prompts/playbooks/`) and orchestrator prompt: delegate to the four
  sub-agents, reconcile (e.g. zone from map vs text), record ambiguities, call `submit_study`.
- Enable the four sub-agents in config.
- `ask_user` tool (LangGraph interrupt, `ClarificationRequest` / `ClarificationReply`) and the eval
  mode where it is disabled and `Case.facts` are given to the agent instead.
- `entrypoints/run.py`: Hydra CLI running a `Case`, writing `VerifiedStudy` JSON and the report
  under `outputs/`.
- Phoenix tracing (OpenInference) switchable by config.
- `README.md` status and run instructions.

**Done when**: the reference case produces a `VerifiedStudy` and a report from the CLI, and the
same study can be requested in the chat UI.
