# Refinements, round 2: envelope, `architect`, destinations

**Status: proposal, not implemented.** The running system follows [REFINE.md](REFINE.md)
and computes a single prism envelope. This document proposes a later architecture; its
contracts, sub-agents and output format do not describe the current code.

---

## 1. Why

The envelope is a single prism: one set-back footprint (one distance per edge kind) times one
height. The reference case (zone UMG, two buildings) does not fit that shape:

| Rule | What it says | What the prism cannot hold |
|---|---|---|
| UMG 6 (p.324) | on the alignment, or set back ≥ 1 m | a choice, not one distance |
| UMG 7 (p.325) | on the separating limit, or set back ≥ 6 m with windows (*vues*), ≥ 3 m without | a choice, and a distance that depends on the facade |
| UMG 8 (p.325–326) | two buildings on one plot: ≥ 10 m apart if a facing facade has windows, ≥ 6 m otherwise | no notion of several buildings |
| UMG 10 (p.326) | 25 m collective-interest, 20 m and R+5 housing, 18 m other uses | one height for the whole site, while the two buildings may have different uses |

Other zones (eval cases e05, e08) have height-dependent setbacks (`H/2, min 4 m`): the allowed
footprint shrinks with height, which a prism cannot show.

## 2. Vocabulary

- **Setback**: minimum distance between a building and one edge of the plot (*recul* from a
  road, *retrait* from a neighbour).
- **Edge kinds**: `road`, `side` (a separating limit that meets the road), `rear` (one that does
  not). Labelled by the gate, as before.
- **Envelope**: the volume the rules allow on the plot.
- **Bounds**: the envelope computed from the rules alone, the regulatory answer.
- **Proposal**: one way to place the program's buildings inside the bounds, chosen by the
  `architect`.

## 3. Sub-agents

The `architect` (REFINE §1, proposed) is added now.

| Name | Real-life role | Output | Submit tool |
|---|---|---|---|
| `architect` | produces the capacity study: turns the cited rules into envelope inputs and places the buildings | `EnvelopeSubmission` → `EnvelopeStudy` | `submit_envelope` |

`planning_lawyer` and `permit_officer` stay in the roadmap. The planning lawyer's reading work
becomes a third `doc_analyst` task, `destinations` (§4a); the decision (each building's
destination and verdict) stays with the orchestrator. A `planning_lawyer` with a typed output
comes back only if evals show the orchestrator misclassifies or keeps destination, height and
parking inconsistent.

## 4. Run order (study playbook)

1. `surveyor`: the site.
2. `zoning_analyst`: the zone.
3. `doc_analyst` **three times in parallel**: `rules`, `oap`, `destinations`.
4. The orchestrator decides each building's destination and admissibility, from
   `notes.destinations`.
5. **`architect`**: needs the site, the `rules` and `oap` notes and each building's destination.
6. The orchestrator assembles the study and calls `submit_study`.

## 4a. `doc_analyst` task `destinations`

**Why**: today the orchestrator classifies each building from the `uses` and `definitions` notes
of `rules`, and nothing asks for the PLU's definitions of the destinations. The classification
drives admissibility, the height (UMG 10: 25 m collective interest, 20 m housing, 18 m other) and
parking (UMG 12 student residences, Titre I cap), so it gets its own reading task.

**Task** (written by the orchestrator, same pattern as `rules` and `oap`):

- label: `destinations`
- aim: classify each building of the program into a PLU destination and sub-destination, and say
  what the zone allows for it.
- topics:
  - `destination_definitions`: how the PLU defines the destinations and sub-destinations that
    could fit the program (housing, hosted accommodation, collective-interest facilities...);
  - one topic per building, named after it (e.g. `residence_sociale_etudiante`,
    `residence_jeunes_actifs`): the candidate destinations, the one that fits and why, and what
    the zone's articles 1–2 say for it;
  - `special_rules`: provisions specific to these uses anywhere in the corpus (e.g. the Titre I
    parking cap for student residences), and the height or parking band each destination falls
    into.
- open points: every classification that is arguable, with the candidate destinations as
  options. The gate turns each into a required `Ambiguity`, as for the other notes.

`DocNotes` already accepts any topic list and requires one note per topic, so no code change.

**Knock-ons**

- `rules` loses its `uses` topic (moved here); its notes get smaller.
- `policies.study.required_notes` becomes `[rules, oap, destinations]`.
- The playbook's admissibility step reads `notes.destinations`; the destination retained for a
  building is the one used for its `BuildingLimits` height (architect) and its parking rule.

**Cost**: measured on a UI run (Haiku, 2026-10-17), the `oap` task cost $0.025 for 20 tool
calls and `rules` $0.070 for 26; `destinations` is `oap`-sized (4 topics), runs in parallel, so
about +$0.02–0.03 per study and no added wall time.

## 5. `architect`

**Job**: translate the `rules` notes into `EnvelopeRules`, then design a `Layout` for the
program's buildings, check it on the preview, and submit both. Code computes everything.

**Does not read the documents.** Every value it submits comes from a cited note. If a rule it
needs is missing from the notes (spacing between buildings, whether building on the limit is
allowed...), it submits an open point instead of guessing; the orchestrator re-runs
`doc_analyst` with that topic or records an `Ambiguity`.

**Inputs** (task text): the buildings, each with its destination as decided by the orchestrator
from `notes.destinations`, the program text, and whether the OAP applies. It reads the `site`,
`notes.rules` and, when the OAP applies, `notes.oap` artifacts itself.

**OAP**: the bounds come from the regulation alone. The OAP is a compatibility requirement (a
project must not contradict it), so it shapes the proposal, not the bounds. Measured on the
reference run, the OAP prescriptions that bear on the volume: heights stepped to an average of
R+4 for residential buildings, building on the street alignment without a continuous front,
ground floors opening onto the street. The layout lists the OAP prescriptions it follows and
how (`Layout.oap`).

**Tools**

| Tool | What it does |
|---|---|
| `read_artifact` | reads `site`, `notes.rules` and `notes.oap` in full |
| `preview_envelope(rules, layout)` | runs the computation below, stores nothing; returns a text summary (per scenario and for the proposal: ground area, height, volume per building, whether the buildings fit, warnings) and a plan image (plot outline, setback strips, each building's part labelled with its name and height, the spacing gap), drawn on the parcel-scale map of `site_view` |
| `submit_envelope(rules, layout, open_points)` | same computation; stores the `EnvelopeStudy` under the `envelope` artifact and replies with the same summary; rejected submissions return `field.path: message` errors |

**Steps**

1. Read `site`, `notes.rules` and, if the OAP applies, `notes.oap`.
2. Fill `EnvelopeRules`: one `SetbackRule` per edge kind, one `BuildingLimits` per building
   (height from its destination), the spacing between buildings, the footprint and green caps.
3. Draft a `Layout` compatible with the OAP; call `preview_envelope`; look at the image and the
   figures; adjust (cut direction, share, which building goes where, windows on the facing
   facades, building heights within the OAP objective). Repeat.
4. Submit. A later submission replaces the earlier one.

**Model**: node `models.nodes.architect`, Haiku like every node, overridable from the config.

## 6. Contracts (`src/agent/contracts/`)

`EnvelopeParameters` and today's `Envelope` are deleted. `Study.envelope` is removed: the
envelope comes from the `envelope` artifact.

```python
# envelope.py: what the architect submits
class Distance(Contract):  # max(min_m, height_ratio × H); at least one set
    min_m: float | None  # "at least 6 m"
    height_ratio: float | None  # "H/2" -> 0.5
    rule: str  # the rule restated
    citations: tuple[Citation, ...]  # >= 1, copied from notes.rules


class SetbackRule(Contract):  # one per edge kind
    kind: BoundaryKind
    on_limit_allowed: bool  # may build right on the edge
    with_windows: Distance | None
    without_windows: Distance | None


class BuildingLimits(Contract):  # one per building of the program
    building: str  # same label as in Study.admissibility
    max_height_m: Limit  # chosen from the building's destination
    max_storeys: Limit  # reported, not used in volumes (§7)


class EnvelopeRules(Contract):
    setbacks: tuple[SetbackRule, ...]  # exactly one per edge kind
    buildings: tuple[BuildingLimits, ...]  # >= 1
    spacing_with_windows: Distance | None  # between buildings on one plot
    spacing_without_windows: Distance | None
    max_footprint_ratio: Limit
    min_green_ratio: Limit


class Layout(Contract):  # the architect's design choices (none dictated by the PLU)
    cut: Literal["across_long_axis", "along_long_axis"]  # long axis of the ground footprint
    first_share: float  # (0, 1): share of the usable area given to the first part
    order: tuple[str, ...]  # building labels, first part first (part 1 = nearer the road)
    facing_windows: bool  # a facing facade has windows -> spacing_with_windows applies
    heights_m: tuple[float, ...] = ()  # per building in `order`, <= its max; empty = the max
    oap: tuple[OapChoice, ...] = ()  # the OAP prescriptions the layout follows
    reasons: str


class OapChoice(Contract):
    prescription: Rule  # cited from notes.oap
    how: str  # how the layout follows it, e.g. "residence_jeunes_actifs at 15 m (R+4)"


class EnvelopeSubmission(Contract):
    rules: EnvelopeRules
    layout: Layout
    open_points: tuple[OpenPoint, ...] = ()


# envelope.py: what code computes
class Level(Contract):  # one horizontal slice
    from_m: float
    to_m: float
    area_m2: float


class BuildingMassing(Contract):
    building: str
    footprint: Polygon  # its ground part
    footprint_area_m2: float
    max_height_m: float
    levels: tuple[Level, ...]  # one slice for a prism, several when setbacks grow with H
    volume_m3: float


class Scenario(Contract):
    name: str  # "largest" | "windows" | "proposal"
    footprint: Polygon | None  # plot minus setbacks at ground level
    footprint_area_m2: float
    buildings: tuple[BuildingMassing, ...]
    fits: bool  # every building fits with the required spacing
    total_volume_m3: float
    assumptions: tuple[str, ...]


class EnvelopeStudy(Contract):  # the `envelope` artifact
    rules: EnvelopeRules
    layout: Layout
    site_area_m2: float
    min_green_area_m2: float | None
    bounds: tuple[Scenario, ...]  # "largest", "windows": from the rules alone
    proposal: Scenario  # from the rules and the layout
    open_points: tuple[OpenPoint, ...]
```

`VerifiedStudy.envelope` becomes an `EnvelopeStudy`.

## 7. Computation (`src/agent/runtime/geometry/`, plain code)

1. **Edges**: labelled road / side / rear by the gate's existing rule, after the surveyor's
   declared public parcels (§10).
2. **Bounds**, two fixed scenarios, independent of the layout:
   - `largest`: each edge kind uses its smallest allowed distance, 0 where `on_limit_allowed`.
     The legal maximum.
   - `windows`: each edge kind uses `with_windows` (falling back to `without_windows`, then 0
     if building on the limit is allowed). The realistic case for housing.
   Each is one massing per building height band, without a split: the bounds answer "how much
   may be built", not "where".
3. **Levels**: the footprint at height `h` is the plot minus each edge's distance at that height,
   `max(min_m, height_ratio × h)`. Slices of `envelope.level_step_m` (config, 1 m); consecutive
   slices with the same area merge, so fixed setbacks give one slice (a prism).
4. **Proposal**: the `windows` ground footprint is cut in two (or more) parts along the layout's
   axis, at the position giving the first part `first_share` of the area, with a gap of the
   spacing that applies (`facing_windows`). Parts are assigned to buildings in `order`; each
   part rises to its layout height (`heights_m`, default its maximum), in levels as in step 3. `fits` is false, with the
   reason, when a part is empty or the gap does not fit.
5. **Caps**: when the total ground area exceeds the footprint-ratio cap or the site area minus
   the minimum green area, every building's area is scaled down by the same factor and an
   assumption is recorded.
6. **Storeys**: `max_storeys` is reported, not converted into metres (that would need a
   floor-to-floor height the PLU does not give).

Later (roadmap): per-edge choice of building on the limit in the layout; splits driven by the
program's floor areas; a third bound "no windows".

## 8. `submit_study` gate

- Reads the `envelope` artifact (producer `architect`) instead of `Study.envelope`, and
  recomputes bounds and proposal from the stored rules and layout: a stored figure cannot drift
  from the code's.
- Every citation in `EnvelopeRules` must appear in `notes.rules`, and every citation in
  `Layout.oap` in `notes.oap` (same doc, page and quote), otherwise rejected: the architect
  cannot bring in unchecked sources. A layout height above the building's maximum is rejected.
- `BuildingLimits.building` labels must match `Study.admissibility` building labels one to one.
- The architect's open points follow the notes' rule: each needs an `Ambiguity` with the same
  question.
- Required notes: `rules`, `oap` and `destinations`; the open-point check covers every
  `notes.*` artifact present, not only the required labels (re-asked labels such as
  `rules_parking` included).
- On acceptance, the reply lists the bounds and the proposal figures.

## 9. Other changes

| Where | Change |
|---|---|
| `doc_analyst` `rules` checklist (playbook) | topics added: setback options per edge kind (on the limit allowed, with / without windows, height formulas), heights per destination, spacing between buildings on one plot; `uses` moves to `destinations` (§4a) |
| Submissions final once accepted | measured: `rules` submitted three times (one cut off by `max_tokens`, one accepted, one unrequested resubmission), `zoning_analyst` three times. The submit tools' acceptance reply ends with "you are done: reply with a short summary and stop"; the sub-agent prompts say never to resubmit after acceptance |
| `doc_analyst` output cap | `models.nodes.doc_analyst.max_tokens` 16000 → 32000: a 14-topic `rules` submission is about 16k output tokens and was cut off (Haiku 5.5 allows 128000) |
| Report (`runtime/report/`) | envelope section: a table per bound, then the proposal (per building: ground area, height, volume, fit) with the layout's reasons and the assumptions |
| Chat UI (`ui/src/components/study/`) | the study view (key figures, limits table, site plan, 3D volume) reads today's `study.envelope` parameters and `envelope` prism; ported to `EnvelopeStudy`: bounds and proposal, one 3D massing per building stacked from its `levels` |
| Config | `conf/subagents/architect.yaml`, `prompts/subagents/architect.md`, `models.nodes.architect`, `envelope.level_step_m`; `subagents` default gains `architect` |
| Evals | an `architect` component set becomes possible: seeded `site`, `notes.rules` and destinations as fixtures, `EnvelopeStudy` scored |

Code placement: contracts in `contracts/envelope.py` (the deleted parameters leave
`contracts/geometry.py`); computation in `runtime/geometry/{envelope,levels,split}.py`; preview
image in `adapters/geo/` (reusing `draw_outlines`); tools in `tools/envelope/`; gate changes in
`tools/study/`.

## 10. `surveyor`: neighbouring parcels declared public

**Why**: the gate labels an edge road when nothing lies across it (public land), and side or
rear when a parcel does. On the reference case, a 116 m² strip parcel, CR0249, lies between
CR0247 and rue Joliot Curie: the street edge faces a parcel, no edge meets the road, and every
edge is labelled rear. The street side then gets the neighbour setback (6 m with windows)
instead of the alignment rule (on the alignment or ≥ 1 m), the OAP's "build on the alignment"
cannot be followed, and the last run's footprint fell from 5,952 m² to 4,241 m². The strip is
most likely pavement or verge never transferred to the town.

**Decision**: the `surveyor` may declare a neighbouring parcel as public land, with its evidence.
This replaces REFINE / V1_PLAN's "neutral edges only" rule: the cadastre fact is kept, the
judgement is added on top and stays visible.

```python
class PublicParcel(Contract):
    id: str  # a parcel touching the site, e.g. "91272000CR0249"
    reason: str  # the evidence: shape, size, position, what the aerial photo shows


class ParcelChoice(Contract):  # fields unchanged, plus:
    public_parcels: tuple[PublicParcel, ...] = ()
```

**What code does** (`parcel_finalizer`, `site_edges`):

- Rejects a declared parcel that does not touch the site, or that is also in `parcel_ids`.
- An edge whose neighbours are all declared public gets `other_side: public_land`; its
  `neighbours` still lists them, so the report can say "public land (CR0249, declared by the
  surveyor)".
- The gate's labelling rule is unchanged: that edge becomes road, the parcel limits meeting it
  side, the others rear.

**Prompt** (`prompts/subagents/surveyor.md`): after choosing the site, look at the parcels along
the street side; if a thin parcel lies between the site and the road and `site_view(kind="aerial")`
shows pavement, verge or road, declare it with the evidence and add an assumption.

**Report and evals**: the site section lists the declared public parcels with their reasons; the
`surveyor` CR0249 trap item checks both the chosen site (CR0247) and the declared strip (CR0249).
