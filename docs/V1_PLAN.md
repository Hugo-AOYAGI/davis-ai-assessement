# v1 plan

How [REFINE.md](REFINE.md) is applied to the v0 code. REFINE says *what* and *why*; this file
fixes the seams (names, contracts, signatures) and who owns which files, so work packages can run
in parallel. Anything REFINE leaves open is decided here.

## Decisions beyond REFINE

| Point | Decision |
|---|---|
| Georeferenced zoning plan (v0 WP3) | **Removed**: `runtime/georef/`, `tools/map/`, the `corpus.zoning_map` block and its control points. `zoning_analyst` finds the site by eye (REFINE §4). |
| `ParcelChoice.address` | Added: the geocoder label, needed to build the `Site` (REFINE's example omits it). |
| `public_parcel_ids` (v0) | Removed: edges are neutral; a strip between plot and street is a `parcel` edge, labelled by the gate's fixed rule. |
| `ZoneFindings.region` | An `ImageRegion` (`doc`, `page`, `region`), like `doc_analyst`'s views, so several plan sheets work. |
| `zoning_analyst` tools | `list_documents` added, to find the plan's document id without hardcoding it. |
| Stored crops | Saved by the `submit_study` gate (zone region + every note view) under `policies.evidence.crops_dir`, deterministic file names; listed in `VerifiedStudy.evidence`. Submit tools only check that regions are valid. |
| Page images | Rendered on demand from the source PDFs (native raster for scanned pages, `render_dpi` otherwise). Ingestion no longer renders images (`Page.image` and `corpus.images` removed). |
| Open point ↔ ambiguity | Matched on the question text (case and whitespace folded): the orchestrator copies the open point's question into the `Ambiguity`. |
| Topic coverage | `DocNotes.topics` echoes the task's checklist; `submit_notes` requires a note per topic and no note outside the list. |
| Tool names | `geocode` (was `geocode_address`), `find_parcels`, `describe_parcels`, `site_view`, `list_documents`, `list_sections`, `read_section`, `search`, `read_pages`, `view_image`, `zoom`, `submit_parcel`, `submit_zone`, `submit_notes`, `submit_study`, `read_artifact`. Deleted: `preview_site`, `view_map`, `view_legend`, `read_zone`, `read_article`, `get_definition`, `compute_envelope`. |
| Artifact keys | `site`, `zone`, `notes.<label>` (e.g. `notes.rules`, `notes.oap`), `study`. |
| Default retrieval | `full_sections` (REFINE §5). |

## Contracts (`src/agent/contracts/`)

```python
# evidence.py (Citation, CitationCheck, Rule, Limit, Resolution, Ambiguity unchanged)
class ImageRegion(Contract):    # doc: str; page: int >= 1; region: (x0, y0, x1, y1) ints,
                                # overview pixels of view_image, x1 > x0 >= 0, y1 > y0 >= 0
class StoredCrop(Contract):     # region: ImageRegion; pixels: (x0, y0, x1, y1) full resolution;
                                # path: str (PNG, POSIX, relative to the project root)

# findings/site.py
class ParcelChoice(Contract):   # address, parcel_ids (>= 1), rationale, assumptions = ()
class EdgeSide(StrEnum):        # PARCEL = "parcel", PUBLIC_LAND = "public_land"
class Edge(Contract):           # start: Point, end: Point, length_m >= 0, other_side: EdgeSide,
                                # neighbours: tuple[str, ...] = ()  (parcel ids across the edge)
class Parcel(Contract):         # unchanged
class Site(Contract):           # address, longitude, latitude, choice: ParcelChoice,
                                # parcels (>= 1), polygon, area_m2 > 0, edges (>= 1),
                                # citations (>= 1, geometric)

# findings/zone.py
class LegendItem(Contract):     # item, applies: bool, note
class ZoneFindings(Contract):   # zone, overlays: tuple[LegendItem, ...] (>= 1), rationale,
                                # region: ImageRegion, ambiguities = ()

# findings/notes.py
class Note(Contract):           # topic, text, citations (>= 1), views: tuple[ImageRegion, ...] = ()
class OpenPoint(Contract):      # question, options = (), why, citations = ()
class DocNotes(Contract):       # label (^[a-z][a-z0-9_]*$), topics = (), notes (>= 1),
                                # open_points = ()

# geometry.py: Polygon, BoundaryKind, Boundary, EnvelopeParameters, Envelope unchanged.

# study.py (Verdict, Admissibility, ParkingBasis, ParkingRule move here from findings/regulation.py)
class Regime(Contract):         # zone, overlays: tuple[LegendItem, ...] (applying items),
                                # oap_applicable, oap_prescriptions: tuple[Rule, ...] = (),
                                # citations (>= 1)
class Study(Contract):          # unchanged fields
class VerifiedStudy(Contract):  # study, site: Site, boundaries: tuple[Boundary, ...]
                                # (edges labelled by the gate), zone: ZoneFindings,
                                # envelope, citation_checks, evidence: tuple[StoredCrop, ...]
```

Deleted: `findings/map.py`, `findings/oap.py`, `findings/regulation.py`, `SiteContext`.

## Shared seams

- **`submit_tool(*, name, artifact, contract, finalize=None, summarize=None)`**
  (`tools/submit/factory.py`): `name` is the tool name; `artifact` is the state key and may hold
  `{field}` placeholders filled from the submission's top-level fields (`notes.{label}`);
  `summarize(stored) -> str` is appended to the `<key> accepted.` reply.
- **`label_edges(edges, *, snap_tolerance_m, collinear_angle_deg) -> tuple[Boundary, ...]`**
  (`runtime/geometry/edges.py`): `public_land` → road; runs of consecutive, nearly collinear
  `parcel` edges form one limit; a limit meeting a road edge at either end → side, else rear.
  **`site_edges(polygon, neighbours, *, snap_tolerance_m, min_shared_ratio) -> tuple[Edge, ...]`**
  (same file): neutral edges, `neighbours` maps parcel id to its metric geometry.
- **`compute_envelope(polygon, boundaries, parameters, *, quad_segs, min_area_m2)`**
  (`runtime/geometry/envelope.py`): max footprint = min(set-back footprint, ratio × site area,
  site area − min green area).
- **`PageImages`** (`adapters/images/pages.py`), built from config: `overview(doc, page)`,
  `zoom(region)`, `check(region)` (raises `RegionError`, a `ValueError` written for the model),
  `save_crop(region, directory) -> StoredCrop`. Overviews and zooms carry pixel rulers labelled in
  overview coordinates; every returned image fits `max_image_px` (≤ 2000).
- **`ImageryClient`** (`adapters/geo/`): IGN Géoplateforme WMS `GetMap`, `map` and `aerial`
  layers, cached on disk like the other geo services.

## Configuration

| Group | Content |
|---|---|
| `conf/geo/default.yaml` (new) | geocoder, cadastre, imagery, surveyor settings and `edges` knobs (shared by `surveyor`, `site_view` and the gate) |
| `conf/images/default.yaml` (new) | `pages`: the `PageImages` node (render dpi, overview / image size, upscale cap, ruler step, crop size, cache size) |
| `conf/corpus/default.yaml` | `legal_force` per document; `zoning_map` and `images` blocks removed |
| `conf/subagents/` | `surveyor.yaml`, `zoning_analyst.yaml`, `doc_analyst.yaml`; the v0 four deleted |
| `conf/models/default.yaml` | nodes `orchestrator`, `surveyor`, `zoning_analyst`, `doc_analyst` |
| `conf/agent/default.yaml` | tools `read_artifact`, `submit_study` (no `compute_envelope`) |
| `conf/policies/default.yaml` | `evidence.crops_dir`; the gate's `notes` labels (`rules`, `oap`) |

## Work packages

```
P1 Foundations ──┬── P2a Site (surveyor, site_view)
                 ├── P2b Documents (text + image tools, zoning_analyst, doc_analyst, ingest)
                 └── P2c Study (gate, playbook, orchestrator, report, run)
                                      └── P3 Integration (merge, full checks, reference run, docs)
```

| WP | Owns |
|---|---|
| P1 | `src/agent/contracts/`, `src/agent/tools/submit/factory.py`, `src/agent/runtime/geometry/{edges,envelope}.py` (`boundaries.py` removed), `src/agent/runtime/images/`, `src/agent/adapters/images/` (was `adapters/raster/`), `conf/images/`, the `geo` and `images` entries of `conf/config.yaml` defaults with a `conf/geo/default.yaml` holding only `edges`, their tests |
| P2a | `src/agent/adapters/geo/`, `src/agent/runtime/geometry/{parcels,projection}.py`, `src/agent/tools/geo/`, `conf/geo/`, `conf/subagents/surveyor.yaml`, `prompts/subagents/surveyor.md`, their tests |
| P2b | `src/agent/adapters/corpus/`, `src/agent/ingest/`, `src/agent/tools/documents/` (was `tools/regulation/`), `src/agent/tools/images/` (replaces `tools/map/`), `conf/corpus/`, `conf/retrieval/`, `conf/images/`, `conf/subagents/{zoning_analyst,doc_analyst}.yaml`, `prompts/subagents/{zoning_analyst,doc_analyst}.md`, their tests |
| P2c | `src/agent/tools/study/`, `src/agent/tools/submit/reader.py`, `src/agent/runtime/report/`, `src/agent/agents/`, `src/agent/entrypoints/`, `conf/{config,agent,models,policies}`, `prompts/{orchestrator,playbooks}/`, `scripts/`, their tests |
| P3 | everything left: merges, cross-package fixes, `README.md`, `CLAUDE.md`, `docs/` |

Every WP deletes the v0 code it replaces, with its tests, config and prompts: no stale names may
remain in the files it owns. P1 lands first and changes the contracts in their final form, so
code owned by P2 packages stops type-checking until they port it. Done for P1 and P2 means
`ruff format` and `ruff check` clean, and `ty check` and `pytest` clean on the files and tests the
WP owns; P3 makes the whole repository clean.

## As built

Where the merged packages depart from, or add to, the seams above.

| Point | As built |
|---|---|
| `describe_parcels` | `describe_parcels(ids, longitude, latitude)`: takes the geocoded address point too (as `find_parcels(longitude, latitude)` does). |
| `site_view` scales | `scale` is `town`, `neighbourhood` or `parcel` (fits the parcels with a margin); `parcel` is the default. The tool node lives in `conf/geo` (`geo.site_view`); sub-agents list it as `- ${geo.site_view}`. |
| HTTP adapter | `adapters/http.py`, one level up from `adapters/geo/`, shared by the geo services (`CachedHttp`); `ServiceError` replaces v0's `GeoServiceError`. |
| Shared page images | `adapters/images/shared.py`: `page_images(...)` is a cached factory, so every `${images.pages}` interpolation gets the same `PageImages` (one cache of decoded pages). |
| Topic coverage | Validated by `DocNotes` itself (model validator: a note per topic, none outside `topics`), not only by `submit_notes`. |
| Scanned pages | `images.pages.scan_min_coverage`: a page whose largest image covers this share of it is a scan (native raster used). |
| Policies | `policies.study.required_notes` (the `doc_analyst` labels the gate requires, `[rules, oap]`) and `policies.evidence.crops_dir` (`data/crops`). |
| Gate wiring | `submit_study_tool` takes config bundles, visible in `conf/agent/default.yaml`: `StudyInputs` (`tools/study/inputs.py`: artifact and producer of `site`, `zone`, `notes.{label}`, plus the required labels), `GeometrySettings` (`tools/study/gate.py`: edge and envelope knobs), `CitationRules` (`tools/study/checks.py`, built by `citation_rules`). |
| Report | `runtime/report/program.py` (was `envelope.py`): admissibility, parking and envelope sections. |
| Run outputs | The CLI copies the study's evidence crops into `<run_dir>/evidence/`; `report.md` links them there. |
| Tool images | Stored by reference: image tools write PNGs to `images.store` (`data/images`, content-addressed) and reply with `{type: image, url}`; `InlineImagesMiddleware` inlines them in each model request only; the Agent Server serves them at `/images/<id>.png` (`entrypoints/http.py`). |
