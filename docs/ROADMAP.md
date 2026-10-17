# Roadmap and deferred decisions

What was intentionally left out of v1, what is still to be designed, and what was considered and
rejected. v1 scope is in [DESIGN.md](DESIGN.md) as refined by [REFINE.md](REFINE.md). Rule of
thumb: an item moves into scope when an eval failure or a concrete need justifies it, and each
move is recorded as a before/after comparison.

Build order: thin end-to-end v0 → v1 refactor ([REFINE.md](REFINE.md)) → eval set → eval-driven
iteration.

---

## 1. Improvements after v1

### Rules and study schema
- **Typed rule catalogue** replacing free-text rules: `Setback(boundary_type, min, f(H))`,
  `MaxHeight(ref, value, storeys)`, `MaxFootprintRatio`, `MinDistanceBetweenBuildings(f(H))`,
  `Alignment / BuildToLine`, `NonBuildableArea(geom)`, `MinGreenRatio`,
  `ParkingRatio(destination)`, each with `applies_if` conditions and citations, plus a
  `QualitativeRule` catch-all that is reported but not computed. Enables rule-by-rule scoring.
- **Richer `Study`**: more typed fields beyond the v0 core, moving towards a claims ledger where
  every claim has a value, unit, status and citations.

### Envelope
- **Stepped 2.5D envelope**: allowed footprint computed per height level, then stacked, so that
  height-dependent setbacks and prospect rules are handled.
- **Two-building fit test**: check that two buildings fit with the article 8 minimum distance,
  using a simple split along the parcel's main axis, and report the max volume per building.
- **3D visualisation** in the UI from the envelope geometry (GeoJSON + heights → mesh).

### Program
- **`ProgramSpec` parse step** (buildings, stated use, known and missing facts) if evals show
  the agent misreads programs.

### Sub-agents
Split out of the orchestrator when evals show failures there (names from REFINE §1):
- `planning_lawyer` (*juriste en urbanisme*): program → destinations → admissibility verdict.
- `architect` (Opus): rules → envelope parameters → capacity study.
- `permit_officer` (Opus, *instructeur*): would this file be rejected, on which article?
  Contradictions, missing rules, unhandled ambiguities, reviewed before `submit_study`.

Unstable stage-like steps may be hardened into deterministic tools without changing the
architecture.

### Site and zoning plan
- **`surveyor` address retries** with spelling variants when the geocoder match is poor.
- **Full candidate list in the `surveyor` output** if evals need to score the shortlist, not only
  the chosen parcels.
- **Georeference the zoning plan once per corpus** (control points in corpus config) if evals
  show `zoning_analyst` often mislocates the site; code then draws the parcel outline on the plan
  crop.

### Citations
- **Cite by note id**: the orchestrator references `doc_analyst` notes instead of copying quotes,
  if evals show quote drift (the v0 reference run had none: 46/46 verified).

### Ingestion and retrieval
- **Ingestion on upload**: an internal API so the UI can ingest new documents, on top of the
  offline `ingest` entrypoint.
- **Retrieval ablation**: `navigation` vs `full_sections` compared in evals.

### Clarifications
- **`simulated` user mode**: a scripted user answers `ask_user` questions from an answer key,
  so we can evaluate whether the agent asks the right questions.

### Models
- **Model ablations**: all-Sonnet vs tiered vs all-Opus on extraction and synthesis.
- Exact per-node split revisited once pricing and eval cost are measured against the ~$250 budget.

### Géoportail de l'Urbanisme
- Not used by the agent. Candidate **eval oracle** for zone/overlay ground truth on generated
  eval addresses (watch for PLU version mismatch with the 2021-07-06 documents).

## 2. Design details parked for later

These were deliberately not designed yet (top-down first); decide when building the brick.

- **LLM caching strategy**.
- **Phoenix experiment layout**: projects, datasets, how Hydra runs map to experiments.
- **Eval design (Part 2 of the brief)**. Already agreed principles:
  - sub-agents evaluated standalone through their typed outputs,
  - only program facts are pre-supplied in evals, never regulatory interpretations,
  - generic interface allows extra eval cases (other addresses, other programs),
  - a separate eval for clarification questions.
  Still to decide: what exactly is evaluated, how expected answers are built, scoring and
  tolerances, citation correctness, anti-gaming, lucky-answer vs grounded-reasoning detection.

## 3. Tooling and standards candidates

Proposed but not adopted yet:
- `scripts/check_structure.py` enforcing ≤250 lines per file and ≤5 files per folder.
- pre-commit hook running ruff, ty, pytest and the structure check.
- import-linter contract enforcing the layering `contracts ← runtime ← adapters ← tools ← agents ← entrypoints`.
- Function limits: ≤40 lines, ≤5 parameters.
- Thin tools: ≤20 lines, delegating to `runtime/` or `adapters/`.
- Ban on dumping-ground modules (`utils.py`, `helpers.py`, `common.py`).

## 4. Considered and rejected

| Option | Why rejected |
|---|---|
| Fixed LangGraph pipeline | Locks the agent into one task; playbooks + typed sub-agents keep flexibility and evaluability |
| GPU zoning used by the agent | Regulatory data outside the attached documents; possible version mismatch |
| Computing every ambiguity scenario | 2^n combinations; ambiguities are resolved by `ask_user` or one justified choice |
| Vector RAG over the regulation | Top-k retrieval misses exceptions; the documents have a clear article structure |
| LLM computing geometry | Not reproducible or testable; geometry is deterministic code |
| True 3D CSG envelope | Too heavy for the timeframe; stepped 2.5D covers the needed rules |
| Free-form Markdown only | Not deterministically scorable; v0 keeps a typed core |
