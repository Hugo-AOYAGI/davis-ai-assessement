# Refinements

Decisions taken after [DESIGN.md](DESIGN.md), brick by brick. **Where this file and DESIGN.md
differ, this file wins.**

---

## 1. Sub-agents

Named after the real-life role that does the job in a buildability study (*étude de capacité*).

| DESIGN.md name | Name | Real-life role | Output | Submit tool |
|---|---|---|---|---|
| `site_locator` | `surveyor` | *géomètre*: which parcels, outline, area | `ParcelChoice` → `Site` | `submit_parcel` |
| `zoning_map_reader` | `zoning_analyst` | reads the zoning plan for a property | `ZoneFindings` | `submit_zone` |
| `regulation_researcher` + `oap_analyst` | `doc_analyst` | reads documents for an aim, cites what they say | `DocNotes` | `submit_notes` |
| `program_qualifier` (later) | `planning_lawyer` (proposed) | *juriste en urbanisme*: classifies uses into destinations | | |
| `envelope_engineer` (later) | `architect` (proposed) | produces the capacity study | | |
| `critic` (later) | `permit_officer` (proposed) | *instructeur*: would this file be rejected, on which article? | | |

The orchestrator plays the project lead: it delegates, decides, and assembles the study.

## 2. Run order (study playbook)

1. `surveyor`: the site.
2. `zoning_analyst`: needs the site to find it on the zoning plan.
3. `doc_analyst` twice in parallel, with two aims: the regulatory rules, and the OAP. Both need
   the zone.
4. The orchestrator decides (destinations, verdicts, numbers, ambiguities), assembles the study
   and calls `submit_study` (plain-code gate).

## 3. `surveyor`

**Job**: turn the address into the site (one parcel or several neighbouring parcels). Facts only:
no zone, no legal labelling of limits, nothing about the envelope.

**Why a sub-agent and not a plain tool**: the reference address needs judgement. Its geocoded
point (the building entrance) lies outside every parcel, BAN links no parcel to the address, and
the nearest parcel is CR0249, a 116 m² strip; CR0247 (5,960 m², 2.5 m away) is the plausible
site. A nearest-parcel rule picks the wrong one. Measured on 2026-10-17:

| Distance | Parcel | Area |
|---|---|---|
| 1.8 m | 91272000CR0249 | 116 m² |
| 2.5 m | 91272000CR0247 | 5,960 m² |
| 22.9 m | 91272000CR0251 | 957 m² |

**Inputs**: the address; the program text, only as context to judge plausibility.

**Steps**

1. **Geocode the address** with `geocode(address)`: normalised address, point, match score.
   If the match is poor or ambiguous, stop and report it (the orchestrator asks the user).
2. **List nearby parcels** with `find_parcels(point)`: id, area, distance, whether the parcel
   contains the point.
3. **Shortlist the plausible ones** (judgement, no tool): keep close parcels that could fit the
   program, drop obvious misfits.
4. **Inspect the shortlist** with `describe_parcels(ids)` (shapes, sizes, whether they touch)
   and, **if doubt remains**, `site_view(ids, kind="aerial")`: an aerial photo with the parcel
   outlines and ids drawn on (see §9). Decide one parcel or several.
5. **Submit the choice** with `submit_parcel(ids, rationale, assumptions)`. Plain code builds the
   `Site`. If rejected (unknown id, parcels that do not touch), fix and resubmit.

**Tools**: all plain code. `geocode` (BAN), `find_parcels` and `describe_parcels` (cadastre,
API Carto), `site_view` (shared, §9). All are geometric sources; responses cached on disk.

**What the agent submits** (`ParcelChoice`):

```json
{
  "parcel_ids": ["91272000CR0247"],
  "rationale": "Address point is on public land, 2.5 m from CR0247. CR0249 (1.8 m) rejected: 116 m² strip, too small for two buildings.",
  "assumptions": ["Cadastre is current; the documents date from 2021-07-06"]
}
```

**What code builds from it** (`Site`, stored in graph state, read by the `submit_study` gate):

```json
{
  "address": "4 Rue Joliot-Curie 91190 Gif-sur-Yvette",
  "choice": {"parcel_ids": ["..."], "rationale": "...", "assumptions": ["..."]},
  "polygon": {"crs": "EPSG:2154", "exterior": [["..."]]},
  "area_m2": 5960,
  "edges": [{"start": ["..."], "end": ["..."], "length_m": 82.3, "other_side": "public_land"}],
  "citations": [{"doc": "BAN", "quote": "91272_1599_00004", "source_kind": "geometric"}]
}
```

The agent never types geometry, so it cannot get it wrong.

**Edges are neutral facts.** Each edge says what lies on the other side: another parcel, or
unnumbered public land (usually a road). Labelling an edge road / side / rear is a legal
classification, done in the `submit_study` gate by one fixed rule in code: public land → road;
an edge between parcels that touches a road edge → side; otherwise → rear. The justification comes
from the lexique definitions of *voie / emprise publique* and *limite séparative*, which
`doc_analyst` returns as cited notes (§5); the orchestrator carries those citations into the study
and records an ambiguity if the PLU definition departs from the fixed rule (e.g. private roads
counted as voies).

**Several parcels**: take the neighbouring parcels that plausibly form one site, state it as an
assumption. The PLU reasons on the *unité foncière* (same owner), which public data cannot show;
the orchestrator may ask the user when it matters.

**Evaluation**: the chosen parcel ids against the expected ones. The reference case is a good hard
case: the naive answer (CR0249) is wrong in a detectable way.

**Later** (ROADMAP): address retries with spelling variants; a full candidate list in the output
if evals need to score the shortlist.

## 4. `zoning_analyst`

**Job**: read the zoning plan and say which zone the site is in and which legend items affect it.
Nothing else. Whether the OAP applies is decided by the orchestrator from `doc_analyst`'s OAP
notes; the OAP perimeter legend item checked here is a cross-check.

**Why a sub-agent**: the plan is one A0 raster image (7021×4966 px) with no coordinates, street
names or parcel numbers. Finding the site means matching it visually against a real map, over
several zoom rounds; reading the zone means dealing with labels outside the crop, zone boundaries
crossing the site, and hatchings. On the overview, neighbouring commune names (Saclay, Orsay,
Bures-sur-Yvette…) and the main roads are legible landmarks.

**Why not merged into `doc_analyst`**: its core is visual localisation, a different skill, and the
zone it returns decides which chapter everyone else reads, so it stays typed and scored on its own.
Can be folded in later if the generic analyst proves able to do it.

**Inputs**: the `Site` from `surveyor` (parcel ids, polygon, address). The model finds the site on
the plan itself; no georeferencing in v0.

**Steps**

1. **See the site in the real world** with `site_view(ids, kind="map", scale="town")` and
   `scale="neighbourhood"`: IGN map with street names and the parcel outline drawn on.
2. **Look at the whole plan** with `view_image(plan)`: spot the legend and the likely area.
3. **Read the legend** with `zoom` on the legend area.
4. **Find the site** by zooming further until the parcel is identified, then read the zone and
   check each legend item (applies / does not apply). If the site straddles a zone boundary,
   record an ambiguity.
5. **Submit** with `submit_zone(...)`. If rejected, fix and resubmit.

**Tools**: `site_view`, `view_image`, `zoom` (all shared, §9). No map-specific tool.

**What the agent submits** (`ZoneFindings`):

```json
{
  "zone": "UMG",
  "overlays": [{"item": "<legend label>", "applies": false, "note": "..."}],
  "rationale": "Site matched by the road layout near the Saclay / Orsay limits; label UMG inside the parcel.",
  "region": [2010, 120, 2260, 300],
  "ambiguities": []
}
```

- `overlays`: one entry per legend item, read by the agent from the legend.
- `region`: the last box zoomed, in overview coordinates: where the agent looked. Code turns it
  into a full-resolution crop stored for the report, and builds the plan citation from it.
- Plan citations are **not** checked against text (the plan has no text layer); the citation
  checker skips them. The stored crop is the audit trail.

**Ingestion**: the zoning plan is only stored as a full-resolution page image. No legend
extraction, no transcription.

**Evaluation**: the zone against the expected one (Géoportail de l'Urbanisme as an independent
oracle); `applies` per legend item against an expected list; optionally whether `region` contains
the site (hand-labelled box for the reference case).

**Later** (ROADMAP): georeference the plan once per corpus (control points in corpus config) if
evals show the site is often mislocated; then code draws the parcel outline on the plan crop.

## 5. `doc_analyst`

**Job**: read documents for a given **aim** and return what they say, as cited notes. One
sub-agent for every document question: the regulatory rules, the OAP, or a chat question ("what
does the PLU say about heights?"). **It extracts, it does not decide**: no destination
classification, no admissibility verdict, no resolved numbers, no choice between interpretations.
The orchestrator does that from the notes, with the program and `ask_user` at hand, and fills the
typed `Study` (admissibility, limits, parking, OAP prescriptions, ambiguities).

**The documents** (the brief gives three; a full PLU has more, e.g. the PADD, which are not
binding on a permit):

| Document | Answers | Legal force | Read by |
|---|---|---|---|
| Zoning plan (*règlement graphique*) | Where is the site? Which zone, which overlays? | binding | `zoning_analyst` |
| Written rules (*règlement*) | What are the hard rules in that zone? | **conformity**: followed exactly | `doc_analyst` |
| OAP (*Orientations d'Aménagement et de Programmation*) | What does the town intend for this area? | **compatibility**: followed in spirit | `doc_analyst` |

**Why a sub-agent**: a lot of reading with cross-references (zone article → general provisions →
lexique; OAP chapter → chapter it builds on), diagrams to read, and it keeps tens of thousands of
tokens of documents out of the orchestrator's context.

**Why free notes rather than typed values**: one kind of judgement per agent (faithful reading
here, legal qualification in the orchestrator, which also owns `ask_user`, matching DESIGN §7);
the same sub-agent serves any aim; typed scoring is kept on the `Study`. Cost: the orchestrator
turns text into numbers (e.g. "H/2, min 4 m"), so its playbook matters more; `submit_study` and
the evals still check that step.

**Inputs** (the task written by the orchestrator):

```json
{
  "label": "oap",
  "aim": "Find what the OAP covering this site prescribes for the program.",
  "topics": ["perimeter", "general_orientations", "building_form", "mobility_access", "landscape_green", "programming", "other"],
  "context": {"zone": "UMG", "legend_items": ["..."], "parcel_ids": ["91272000CR0247"], "program": "..."}
}
```

- `label`: names this run; the notes are stored under it, so parallel runs do not overwrite each
  other.
- `topics`: the checklist the answer must cover, supplied by the playbook; may be empty for a chat
  question.
- `context`: whatever the orchestrator already knows.

**Steps**

1. **Pick the documents and sections** for the aim: `list_documents`, then `list_sections`.
2. **Read them**, following cross-references.
3. **Look at diagrams** when content is in images (`view_image`, `zoom`), compared with
   `site_view` when location matters.
4. **Write the notes**: at least one cited note per topic; list the open points.
5. **Submit** with `submit_notes`. Code verifies every quote on its page and checks that every
   topic has a note. If rejected, fix and resubmit.

**Tools**: all shared (§9): `list_documents`, `list_sections`, `read_section`, `search`,
`read_pages`, `view_image`, `zoom`, `site_view`. Retrieval mode is a config switch; v0 default
`full_sections` (the relevant set fits in context).

**What the agent submits** (`DocNotes`):

```json
{
  "label": "rules",
  "notes": [
    {"topic": "parking",
     "text": "1 space per 150 m² of floor area for student residences; national cap for résidences universitaires overrides it.",
     "citations": [
       {"doc": "plu_reglement", "page": 327, "article": "UMG 12", "quote": "1 place de stationnement par tranche de 150 m²", "source_kind": "regulatory"},
       {"doc": "plu_reglement", "page": 6, "article": "Titre I", "quote": "...", "source_kind": "regulatory"}],
     "views": []},
    {"topic": "building_form",
     "text": "Buildings aligned on rue Joliot-Curie, without a continuous uniform front.",
     "citations": [{"doc": "oap", "page": 34, "quote": "Le principe d'une implantation des constructions à l'alignement le long de la voie doit être retenu", "source_kind": "regulatory"}],
     "views": [{"doc": "oap", "page": 34, "region": [120, 400, 900, 1100]}]}
  ],
  "open_points": [
    {"question": "Which destination covers a Résidence Jeunes Actifs?",
     "options": ["habitation", "CINASPIC"],
     "why": "The term appears nowhere in the PLU.",
     "citations": []}
  ]
}
```

(The two example notes come from different runs; shown together for brevity.)

- `topic`: one of the task's topics.
- `citations`: quotes, verified at `submit_notes` (where the agent that read the text can fix
  them) and again at `submit_study`.
- `views`: image regions (diagrams). Code stores the crops; not verified, like the zoning plan.
- `open_points`: questions only. The orchestrator turns each into an `Ambiguity`, by choosing or
  by asking the user.

### Study task 1: `rules`

**Aim**: the regulatory rules for the program in the zone, plus the provisions of every applying
legend item.

**Topics**: uses, access, networks, setback_road, setback_side, setback_rear,
distance_between_buildings, footprint, height, appearance, parking, green_space, definitions,
other.

**Corpus facts** (checked 2026-10-17): zone UMG is p.320–332, articles 1–16; Titre I general
provisions p.4–11; lexique p.374–379. UMG 12 (p.327) sets 1 space per 150 m² of floor area for
student residences, but Titre I (p.6) adds national caps for résidences universitaires; a correct
note needs both. "Jeunes actifs" appears nowhere: a certain open point. `definitions` must cover at
least hauteur, emprise au sol, voie, emprise publique, limite séparative, espaces verts.

### Study task 2: `oap`

**Aim**: whether an OAP covers the site, and what it prescribes for the program.

**Topics**: perimeter, general_orientations, building_form, mobility_access, landscape_green,
programming, other.

**Corpus facts** (checked 2026-10-17): chapter 8 *Le quartier Joliot Curie* (p.33–36) states that
it **complements chapter 7** *Le site de Moulon* (p.21–32), so both are read. Pages 34–36 each
hold two diagrams carrying prescriptions only shown there (alignment on rue Joliot-Curie,
diagonal pedestrian axis, landscape network). p.36 (programming) plans "constructions
d'habitation destinées aux étudiants", which supports the program. The `perimeter` note compares
the OAP diagrams with `site_view`; the orchestrator cross-checks it with the OAP legend item from
`zoning_analyst`.

**Evaluation**: per study task, coverage of expected facts (rules: parking note citing p.327 with
"150 m²", UMG height limit, 20 % green space, the "jeunes actifs" open point; OAP: site inside the
perimeter, alignment on rue Joliot-Curie, student housing in the programming, chapter 7 cited);
share of citations verified. Typed values are scored on the `Study`.

**Knock-on**: program classification moves to the orchestrator (`planning_lawyer` stays a later
split).

## 6. Orchestrator and study playbook

**v0 as built** (WP6, `prompts/playbooks/study.md`, 8 steps): site → zoning plan → regulation and
OAP in parallel → read the artifacts → reconcile → envelope preview (`compute_envelope`) → submit
→ reply. Program facts asked once in one `ask_user` batch when enabled; quotes copied exactly
from the artifacts.

**Reference run** (2026-10-17, `outputs/2026-10-17/13-39-00` on `wp6-integration`): accepted at the
first submission, 46/46 text-verifiable citations verified, 5 ambiguities recorded, $0.71, 164 s.
Seen in the run:

| Observation | Consequence |
|---|---|
| The envelope preview rejected the parameters and the orchestrator gave up | No footprint or volume in the reply |
| Setbacks 0 m, so footprint = whole site (5,952 m²) | The 20 % green cap (max 4,761 m² built) is only an assumption, not applied |
| "Does the OAP perimeter cover the parcel, given the maps cannot be read?" | OAP diagrams unreadable: confirms the image tools (§9) |
| 46/46 quotes verified, 0 rejections | Copying quotes from sub-agent outputs works: no "cite by note id" in v1 (ROADMAP if evals show drift) |

**v1 playbook** (5 steps):

1. **Frame the request**: address, program; ask missing program facts in one `ask_user` batch
   (in evals: `Case.facts`, `ask_user` off).
2. **Site and zone**: `surveyor` → `Site` (poor address match: ask the user); `zoning_analyst` →
   zone and applying legend items.
3. **Read the documents**: `doc_analyst` twice in parallel, tasks `rules` and `oap` (label, aim,
   topics, context; §5). Read the full outputs `notes.rules` and `notes.oap`, not the replies.
4. **Decide**, following a fixed sub-checklist:
   - regime: zone (cross-check with the zone chapter read), overlays, OAP applicable (`perimeter`
     note cross-checked with the OAP legend item from `zoning_analyst`);
   - admissibility per building: destination and verdict from the `uses` and `definitions` notes;
   - the 7 limits as numbers, formulas resolved at maximum height (e.g. "H/2, min 4 m");
   - parking per use; conditions (other rules, OAP prescriptions);
   - every open point → an `Ambiguity` (chosen + rationale). Product: interpretation questions in
     one `ask_user` batch with a recommended option each. Evals: the orchestrator chooses.
   - if a note is missing or contradicts another, re-ask `doc_analyst` with a precise aim.
5. **Submit and reply**: `submit_study` until accepted (fix every listed error; a failed quote →
   take the quote from the notes or re-ask `doc_analyst`, never invent). Reply with the figures
   the gate returns.

**Changes from v0**: new names and tasks (steps 2–3); a "Decide" step replacing part of
"Reconcile", since notes are no longer typed; **no envelope preview step and no
`compute_envelope` tool**: `submit_study` computes the envelope anyway and returns it on
acceptance, so the failure seen in the run cannot happen. At most two `ask_user` batches per study.

## 7. `submit_study` gate

**v0 as built** (WP5/WP6, `tools/study/gate.py`): validates the `Study`; reads the site from state;
computes the envelope; checks every regulatory citation on its page (similarity ≥ 0.9, `reject`
policy: one error per failed quote); zoning-plan citations recorded as not text-verifiable; a
corpus document cited as geometric is rejected. The same citation check runs in the sub-agents'
submit tools.

**v1 changes**

1. **Return the envelope on acceptance**: buildable footprint, maximum footprint, green area,
   maximum volume, assumptions, so the orchestrator reports them (replaces the preview step).
2. **Apply the green cap**: the maximum footprint is also capped by site area minus minimum green
   area, instead of listing it as an assumption (fix in `runtime/geometry/envelope.py`).
3. **Open points all handled**: every `open_point` in `notes.rules` and `notes.oap` must match an
   `Ambiguity` in the `Study`; otherwise reject, naming the missing point. Deterministic, made
   possible by `DocNotes`.
4. **Edge labels in the gate**: the `Site` keeps neutral edges (§3) and the gate labels them by the
   fixed rule. v0 does the same labelling in code inside `site_locator`; the result is the same,
   the move keeps `surveyor` to facts only.
5. **Map evidence**: `zoning_analyst`'s `region` and `doc_analyst`'s `views` become stored crops,
   recorded like v0's raster citations (not text-verified).

## 8. Applying this file

v0 works end to end, so every change above is a refactor of working code. Order:

1. Merge `wp6-integration` into main as the **v0 baseline**; keep its reference run as the
   "before" (accepted, 46/46 citations, 5 ambiguities, $0.71).
2. Apply this file as **v1**: contracts, renames, `doc_analyst`, shared tools, playbook, gate.
3. Run the reference case again and compare with the baseline: the before/after DESIGN asks for,
   and material for the evals part.

## 9. Shared tools

### Text

| Tool | Returns |
|---|---|
| `list_documents()` | corpus documents with their kind and legal force (conformity / compatibility), from corpus config |
| `list_sections(doc)` | the document's table of contents (from ingestion) |
| `read_section(id)` | one section's text, with page numbers |
| `search(text)` | the best-matching sections (BM25) |
| `read_pages(doc, from, to)` | raw page text, fallback for anything the splitter missed |

These replace `read_article(zone, n)` and `get_definition(term)`, which are only "read a section".

### Images

How Claude reads images (platform docs, checked 2026-10-17): every image is downscaled to the
model's limit, 2576 px long edge / ~4,800 visual tokens for Sonnet 5.5 (~$0.01 per image). The
zoning plan is seen at ~37 %: colours, large labels and commune names stay readable, small labels
and hatchings do not. Anthropic's computer-use toolset solves this with an overview plus
`zoom(region)` in overview coordinates; we copy that pattern in our own tools. Above 20 images
in one request each image must fit 2000 px per side, so every returned image is capped at 2000 px.

| Tool | Returns | Used by |
|---|---|---|
| `view_image(doc, page)` | any corpus page image (zoning plan, OAP diagrams, scanned pages), downscaled to fit, pixel rulers on the edges | `zoning_analyst`, `doc_analyst` |
| `zoom(doc, page, region)` | `[x0, y0, x1, y1]` in overview coordinates, cut from the full-resolution image | `zoning_analyst`, `doc_analyst` |
| `site_view(ids, kind, scale)` | `kind` = `map` (IGN, street names) or `aerial` (orthophoto), parcel outlines and ids drawn by code (geometric source) | `surveyor`, `zoning_analyst`, `doc_analyst` |

Coordinates always refer to the overview, so the model never loses its place across zoom levels.
