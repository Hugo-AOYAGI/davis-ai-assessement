# Design

Regulatory-analysis agent that navigates planning documents (PLU) and produces an auditable
buildability study for a parcel. Reference case: **4 rue Joliot Curie, 91190 Gif-sur-Yvette**,
program = one Résidence Sociale Étudiante + one Résidence Jeunes Actifs in two separate buildings.

Grading weights (from the brief): system design 40% · evals 40% · study quality 20%.

Guiding principle: **start simple, iterate**. Every brick ships in its simplest working form (v0)
and is enriched only when evals show it is needed. See [ROADMAP.md](ROADMAP.md).

---

## 1. Interface

The agent is **generic**: nothing is hardcoded to the reference parcel or program.

| Input | Form | Notes |
|---|---|---|
| Address | free text in the conversation / context box | |
| Program | free text | read directly by the agent (no parsing step in v0) |
| Corpus | `corpus_id` (e.g. `gif-sur-yvette@2021-07-06`) | produced offline by `ingest` |
| Clarifications | answers to `ask_user` | disabled in evals, answers pre-supplied |

The agent is **conversational**: it can answer follow-up questions, explain a rule, or ask for
clarification. On request it produces a **`Study`**, the only artifact scored by the evals.

## 2. Sources

Two kinds of sources, separated in the schema (`Citation.source_kind`):

- **Regulatory** — only the three attached PDFs justify legal/planning conclusions.
- **Geometric / contextual** — public non-regulatory data used to locate and represent the parcel:
  BAN geocoder, cadastre (API Carto / cadastre.data.gouv.fr).

The Géoportail de l'Urbanisme (GPU) is **not used by the agent**: its zoning is regulatory data
and may reflect a newer PLU version than the attached 2021-07-06 documents. It may serve as an
independent oracle in evals.

## 3. Output — `Study` (v0)

Markdown reasoning for humans + a **small typed core** for deterministic scoring.

| Block | Typed fields (v0) |
|---|---|
| Site identification | method, cadastral ids, polygon, parcel area, geometry assumptions |
| Regulatory regime | `zone`, `overlays[]` (including *checked, not applicable*), `oap_applicable` |
| Program admissibility | per building: `{stated_use, destination, verdict}`, verdict ∈ permitted / conditional / restricted / prohibited |
| Envelope | `{parcel_area, setbacks{road, side, rear}, max_height_m, max_storeys, max_footprint_ratio, min_green_ratio}` + computed footprint/volume |
| Feasibility | parking ratios per use, access, networks, other conditions |
| Ambiguities | `{question, chosen, rationale}` |
| Citations | `{doc, page, article, quote, source_kind}` attached to every claim above |

Rules themselves are free text in v0. The Markdown report is rendered from the `Study`.

### Contracts

Every seam between modules is a frozen Pydantic model in `src/agent/contracts/`. Field docstrings
become the JSON-schema descriptions the model reads in `submit_<artifact>` tools.

| Contract | Module | Produced by | Consumed by |
|---|---|---|---|
| `Citation`, `CitationCheck`, `Rule`, `Limit`, `Ambiguity` | `evidence` | every finding | citation checker, scorers |
| `Polygon`, `Boundary`, `EnvelopeParameters`, `Envelope` | `geometry` | `site_locator`, `regulation_researcher`, envelope runtime | envelope runtime, `submit_study` |
| `Case` | `inputs.case` | Hydra `case/`, eval sets | entrypoints, evals |
| `ClarificationRequest`, `ClarificationReply` | `inputs.clarification` | `ask_user` (interrupt / resume) | UI, simulated user |
| `Corpus`, `Document`, `Page`, `Section` | `inputs.corpus` | `ingest` | corpus adapter, citation checker |
| `SiteContext` | `findings.site` | `site_locator` (stored in graph state) | orchestrator, `submit_study` gate |
| `MapFindings` | `findings.map` | `zoning_map_reader` | orchestrator |
| `RegulationFindings` | `findings.regulation` | `regulation_researcher` | orchestrator |
| `OAPFindings` | `findings.oap` | `oap_analyst` | orchestrator |
| `Study` | `study` | orchestrator via `submit_study` | gate |
| `VerifiedStudy` | `study` | `submit_study` gate (adds site, `Envelope`, citation checks) | report renderer, scorers |

Changing a contract is a cross-cutting change: update its tests in `tests/contracts/` and every
producer and consumer in the same change.

## 4. Architecture

```
                         ┌──────────────────────────────┐
  agent-chat-ui ◄──────► │ LangGraph Agent Server       │
                         │  Orchestrator (deepagents)   │
                         │   loads playbook: study      │
                         └──┬───────────┬───────────┬───┘
            task (sub-agent)│           │ tools     │ submit_study (hard gate)
     ┌──────────────┬───────┴────┬──────┴─────┐     ▼
 site_locator  zoning_map_reader  regulation_  oap_analyst     Pydantic validation
     │               │            researcher        │          + citation verification
  BAN/cadastre   map crop+vision  corpus nav     corpus nav    → errors returned to agent
```

- **Orchestrator**: a deepagents agent. It chats, plans, delegates, and assembles the study.
- **Playbooks** (`prompts/playbooks/`): task recipes loaded on demand (e.g. *full study*).
  New tasks are new playbooks, not new graphs.
- **Sub-agents**: each has a typed input and ends by calling a `submit_<artifact>` tool whose
  Pydantic schema is validated. Each sub-agent can therefore be invoked **standalone** in evals.
- **Deterministic tools**: geocoding, cadastre lookup, envelope geometry, citation check. No LLM.
- **Hard gate**: a `Study` is accepted only through `submit_study`, which validates the schema,
  checks required sections, and verifies every citation quote against the corpus. Failures are
  returned to the orchestrator for correction.

### Sub-agents

| Sub-agent | v0 | Responsibility | Output |
|---|---|---|---|
| `site_locator` | yes | address → parcel(s), polygon, boundary types | `SiteContext` |
| `zoning_map_reader` | yes | zone + overlays from the raster zoning plan | `MapFindings` |
| `regulation_researcher` | yes | general provisions, zone chapter, lexique; in v0 also program classification and rule extraction | `RegulationFindings` |
| `oap_analyst` | yes | applicable OAP and its prescriptions (compatibility, not conformity) | `OAPFindings` |
| `program_qualifier` | later | program → destinations → admissibility | `Admissibility` |
| `envelope_engineer` | later | rules → envelope parameters → geometry | `Envelope` |
| `critic` | later | contradictions, missing rules, unhandled ambiguities | `Review` |

Later sub-agents are split out of `regulation_researcher` / the orchestrator **when evals show a
failure there**; each split is documented as a before/after ablation.

## 5. Ingestion

Offline `ingest` entrypoint, run once per corpus, cached on disk under `data/`.

1. A small model (Haiku) classifies each PDF: `regulatory_text | zoning_map | oap`.
2. Type-specific pipeline:
   - `regulatory_text` → section tree by heading regex (zone → article), page anchors kept.
   - `zoning_map` → image + legend stored for cropping and vision.
   - `oap` → sections + figure pages.
3. A raw `read_pages(doc, from, to)` tool remains as fallback for anything the splitter missed.

## 6. Retrieval

Structured navigation, no embeddings: `list_sections`, `read_article(zone, n)`,
`get_definition(term)`, BM25 keyword search. When the relevant set is small (the target zone
chapter + general provisions + lexique + OAP chapter ≈ 25–30k tokens), whole sections are loaded
into the sub-agent context. Both modes are Hydra variants (`retrieval=navigation|full_sections`).

## 7. Ambiguities and clarifications

- `ask_user` tool: a batch of questions, each with proposed options + a free answer.
- Two kinds of questions:
  - **Program facts** (only the client knows): units, floor area, financing, number of buildings.
  - **Regulatory interpretations** (the agent's expertise): use classification, reference
    height, boundary type, OAP bindingness. In the product, offered with the agent's
    recommendation as default.
- **Evals**: `ask_user` disabled. Program facts are pre-supplied; regulatory interpretations are
  **never** pre-supplied — the agent chooses, justifies, and records an `Ambiguity`.
- No multi-scenario computation: one interpretation per ambiguity, one envelope.
- A separate eval checks whether the agent asks the right questions.

## 8. Envelope

- **v0**: prism — buildable footprint (parcel polygon minus setbacks) × max height, plus
  footprint ratio cap. Computed by deterministic code from typed parameters; the LLM never
  computes geometry.
- **Later**: stepped 2.5D (footprint per height level, for height-dependent setbacks), then a
  two-building fit test (article 8 distance between buildings).

## 9. Citations

`{doc, page, article, quote, source_kind}`. The quote must appear verbatim (after normalisation,
fuzzy threshold in config) on the cited page. Unverifiable citations are rejected by
`submit_study` (policy configurable: reject-and-retry or flag).

## 10. Models

All model choices are per node in Hydra (`conf/models/`), enabling ablations.

| Node | Default |
|---|---|
| ingestion classifier, page tagging | Haiku |
| orchestrator, sub-agents (incl. vision on the map) | Sonnet |
| `envelope_engineer`, `critic` (when split out) | Opus |

All LLM calls go through `src/agent/llm/` (caching, cost tracking, tracing). Budget ≈ $250 total.

## 11. Configuration and evaluability

Hydra exposes **every** knob: model/temperature/max tokens per node, enabled sub-agents and
their prompt files, playbook, `ask_user` mode and pre-supplied answers, retrieval mode and tool
limits, corpus and case, citation strictness and policy, geometry tolerances, caching, tracing.
Phoenix (OpenInference) traces every run; each Hydra run is an experiment.

Evaluability hooks:
- typed sub-agent outputs → per-sub-agent evals with fixed inputs,
- typed `Study` core → deterministic scorers,
- config variants → ablations (models, retrieval, sub-agent splits).

## 12. Evolution path

v0 is the simplest working version of each brick. Post-v0 improvements, parked design details,
standards candidates and rejected options are tracked in [ROADMAP.md](ROADMAP.md).

Build order: thin end-to-end v0 → eval set → eval-driven iteration.

## 13. Corpus facts (Gif-sur-Yvette, 2021-07-06)

| Document | Facts |
|---|---|
| `plu_reglement` | 465 p., text layer. Titre I general provisions p.4–11. Zone UMG (Joliot-Curie) p.320–332, articles 1–16. Lexique p.374–379. Reserved sites p.366–372. |
| `plu_reglement_graphique` | single raster A0 JPEG (7021×4966 px), no text layer, no street names or parcel numbers; zone labels and OAP outline legible; no height plan. |
| `oap` | 36 p., text layer. Ch. 8 *Le quartier Joliot Curie* p.33–36; schemas are raster. |

"Jeunes actifs" appears nowhere in the corpus: program classification is a genuine ambiguity.
PDF page numbers = printed page + 1.

## 14. Parked

See [ROADMAP.md](ROADMAP.md) §2. Eval design (Part 2 of the brief) is the main open item.
