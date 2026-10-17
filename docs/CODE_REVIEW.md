# Non-UI code review

Review date: 2026-10-17. Scope: backend, ingestion, contracts, deterministic runtime,
configuration, prompts, evaluations, scripts, tests and project documentation. The `ui/`
directory was excluded: no UI consumer audit or UI changes were part of this review.

## Assessment

The existing architecture is worth keeping. Responsibilities are recognisable, factories are
configured centrally, schemas are shared, and the deterministic core has substantial tests.
A wholesale tree rewrite would add navigation and migration costs without resolving the main
weaknesses: overstated documentation, incomplete evaluation coverage, and gaps between the
validation promises and the checks actually implemented.

Three independent reviews covered contracts/runtime, evaluations, and backend integrations.
Baseline verification passed lint, formatting, strict typing and 793 tests. Findings below
separate implemented fixes from remaining work; passing tooling alone did not reveal these issues.

## Corrected in this review

- **Missing eval datasets could produce successful empty passes.** Dataset selection now rejects
  a missing explicit level and selections with no matching items, before corpus or judge setup.
  Regression tests cover missing datasets and status-filtered empty selections.
- **Documentation presented plans as shipped functionality.** README and EVALS now disclose the
  one verified surveyor benchmark item. The 70-item suite and ground-truth tooling are planned.
  REFINE_v2 is explicitly an unimplemented proposal; REFINE remains the current design baseline.
- **Concurrent HTTP readers could see partial cache files.** Response bodies now publish by
  atomic replacement from a complete temporary file; tests cover publication and cleanup.
- **Invalid geometry inputs reached computation.** Contracts now reject short/empty hole rings,
  non-finite coordinates and limits, negative setbacks, nonpositive heights/storeys, and
  fractional storey counts before the submission gate computes an envelope.
- **Revision aliases bypassed overlap detection.** `items.0` and `items.00` resolve to the same
  list element but previously could crash removals or silently lose a nested edit. Overlap
  checks now operate on resolved paths, with regression tests.
- **Phoenix could omit failed evaluations from the denominator.** The runner now tracks actual
  budget refusals and rejects unexplained missing results, preserving saved records without
  publishing a misleading successful score report.
- **Judge cache identity omitted generation settings.** Cache identity now incorporates the
  resolved model node and structured-output method, alongside prompts, schema and inputs.
- **Dormant eval configuration.** Removed `eval_tasks.artifacts.e2e`: end-to-end execution reads
  the verified study directly, so this setting could not affect behaviour.
- **Judge prompt folder exceeded the five-file standard.** Question prompts are grouped by
  responsibility, and configured paths are updated. Missing private-function docstrings in the
  note scorer were added.
- **Startup lacked a model-free server check.** `scripts/smoke_server.py --startup-only` starts
  the real server, creates an assistant and retrieves its graph schema, then cleans up its
  process tree. The environment template disables tracing until Phoenix is enabled explicitly.

## Remaining correctness and evaluation gaps

### High: benchmark coverage is still one case

`evals/datasets/surveyor/s01_joliot_curie.yaml` is the sole shipped verified benchmark. Examples
under `tests/evals/fixtures/items/` exercise the harness; they do not establish model quality.
There is no measured zoning, document or end-to-end benchmark result, and no published judge
calibration. Implement and independently verify those datasets before claiming broad accuracy.
The README and EVALS now state this limit.

### High: the gate does not reconcile independently submitted facts

`src/agent/tools/study/gate.py::_check` checks open points and citations, but does not establish
that `Study.regime.zone` agrees with the zoning artifact, that applying overlays match, or that
the study address represents the delivered site. The report can therefore display incompatible
zone claims in its regime and zoning-plan sections (`runtime/report/sections.py`).

A follow-up should define when a discrepancy is a rejection and when a cited, explicit ambiguity
may override a map reading. Add conflict tests for zone, overlays and site identity. Blind string
identity is unsuitable for addresses, and an unconditional zone equality rule would prevent a
reasoned correction of a mistaken analyst.

### Medium: zoning ambiguities can disappear from the final study

`tools/study/gate.py::_check` requires ambiguities corresponding to document open points,
but not to `ZoneFindings.ambiguities`. Those findings are visible to standalone zoning evals
and the model through artifacts; the final study can nevertheless omit them. The playbook
instructs the model to retain them, but this is not enforced. Extend the gate's coverage check
if every zoning uncertainty must survive final assembly.

### Medium: corpus identity and server overrides can disagree with execution

`entrypoints/run.py::run_study` records `case.corpus_id` while tools load the corpus configured
by `cfg.corpus.dir`; it does not reject a mismatch. Validate one corpus identity before running.
On the server, logging/tracing (`entrypoints/graph.py`) and the image HTTP store
(`entrypoints/http.py`) are initialised once. Per-run graph overrides do not reconfigure those
process-wide resources. An image-store override can therefore create URLs the HTTP app cannot
serve. Explicitly distinguish run-scoped settings from startup-only settings and reject
incompatible overrides.

### Medium: document checklists are asserted by the model itself

`contracts/findings/notes.py::DocNotes._topics_covered` validates notes against the submitted
`topics`; that tuple can be empty. `tools/documents/notes.py` does not compare it with the original
requested checklist. `tools/study/inputs.py` requires note artifacts by label but does not verify
that an artifact's embedded label matches its state key. The current checks prove internal
consistency, not completion of the original task. Store task requirements separately from outputs
before making stronger coverage claims.

### Medium: failed eval traces can be incomplete

`evals/harness/tasks.py::run_item` retains cost and an error after an exception, but messages from
the failed invocation are not assigned to its outcome. `runs/capture.py` discards errored
sub-agent runs. Successful completed sub-agent traces may survive; the failing run's partial
trajectory may not. Capture model/tool events incrementally if diagnosing failure trajectories is
required. Until then, do not claim that every message before failure is preserved.

### Medium: the computed envelope has deliberate limits

`runtime/geometry/envelope.py` computes one prism and keeps only the largest connected footprint.
Smaller disconnected parts are omitted with an assumption. Storeys, parking ratios, inter-building
spacing and qualitative rules do not constrain this geometry. These are modelled/reportable
findings, not implemented capacity calculations. A two-building fit test and stepped envelope
belong to the explicit round-2 proposal, not a readability refactor.

### Low: classifier bypass still constructs a provider client

`entrypoints/ingest.py` calls `make_classifier` eagerly, and `ingest/classify.py` constructs its
model immediately. Supplying every document's `kind` and `title` skips classifier invocation
but not construction. Lazy construction would let deterministic ingestion run without a model
client when metadata is fully supplied. The default setup still uses model classification.

### Low: artifact templates accept unsupported syntax

`tools/study/inputs.py::StudyInputs._notes_key_has_label` only searches for `{label}`; additional
unknown placeholders pass validation and fail during formatting. Generic submission templates
also accept conversions/specifications beyond the documented top-level-field convention.
Validate supported template syntax at construction, with malformed-template tests.

## Field and configuration usage

The dedicated [Vulture follow-up](DEAD_CODE.md) records detector commands, confirmed unused
data, test-only APIs and framework/configuration false positives.

No public output fields were removed based on a backend-only search. A field can be useful to
a reader or an external client without participating in a numeric score. UI usage was deliberately
not verified.

- **`EnvelopeParameters.max_storeys`:** rendered by `runtime/report/program.py` and included in
  CLI summaries; does not affect `compute_envelope`. Keep it as a reported regulatory limit.
- **`ParkingRule` values:** rendered as ratios in the report; no parking total, fit or feasibility
  calculation consumes them. Keep them and describe that computational limit.
- **Zone rationale, parcel rationale/assumptions and ambiguity options/rationale:** report and
  audit data consumed by `runtime/report/sections.py`; they are not stale simply because they
  do not alter geometry.
- **`Note.views`, zoning region and stored crop coordinates/paths:** validation, evidence export
  and image provenance. Retain the data needed to reproduce and inspect the evidence.
- **`DocNotes.topics`:** actively used for self-consistency validation; its weakness is the
  absence of an independently stored expected checklist, not lack of a reader.
- **`ingest.rules.Line.x0`:** confirmed unused by processing algorithms. Extraction fills it and
  fixture capture preserves it, but splitting reads other line attributes. This is the clearest
  removable transient field; remove it together with fixture/generator inputs in a focused change.
- **Site longitude/latitude:** persisted location provenance exposed to the model through
  artifacts; no additional direct backend/eval calculation found. This is weaker usage than
  geometry but not sufficient evidence for removing a public output field.
- **`StoredCrop.pixels`:** written and validated provenance with no direct backend/report/eval
  reader beyond tests; retained for auditability, with UI use unverified.
- **Geocoder city/postcode/citycode and parcel metrics:** live inputs to tool JSON read by models.
  A field does not need a direct deterministic scorer to be operationally useful.
- **`RunRecord.wall_time_s`:** duplicates `RunRecord.cost.wall_time_s`; `tasks.py` populates both.
  Consolidate in a versioned record migration, preserving loading of existing saved records.
- **`Item.from_items`:** validated provenance for planned end-to-end composition; no shipped
  composition command uses it. Keep only if that provenance remains part of the intended dataset
  format; document that its automation is pending.
- **Judge validation helpers:** tested support code with no operational calibration command or
  published labelled calibration set. They should not be presented as completed judge validation.

## Structure, complexity and standards

The automated review checked source files under `src/`, `evals/`, `scripts/`, `conf/` and
`prompts/`, excluding generated Python caches. Python and configuration/prompt files meet the
250-line limit; folders meet the five-file limit after grouping judge prompts. Test folders are
exempt under the documented standard.

AST inspection found no imports from a higher numbered layer in the documented
`contracts ? runtime ? adapters ? tools ? agents ? entrypoints` ordering, and no runtime imports
from the I/O or agent layers. Strict typing, Ruff complexity (maximum 8), annotation, import and
public docstring checks pass. A separate AST check covers private-function docstrings that Ruff's
public-docstring rules do not fully enforce. Existing narrow lint/type suppressions explain
framework typing and factory signatures; they do not warrant a generic wrapper layer.

The standards are stricter than what tooling enforces: file/folder limits, all private docstrings,
purity and layering are not all automated CI gates. There is no committed CI workflow under
`.github/`. Consider a small architecture/structure check and CI after agreeing which rules are
hard requirements. The ban on configuration values in code also needs a distinction between
tunable policy and fixed protocol/schema constants; moving every fixed label into YAML would
make the code harder to follow. Short model-facing recovery messages/tool protocol descriptions
also remain in Python (`llm/truncation.py`, `tools/submit/`, `tools/interaction/`), contrary to
the literal no-prompt-strings rule. Clarify an exception for stable tool protocol text, while
keeping domain reasoning prompts in Markdown. Shared image primitives (`PixelBox`,
`OverviewScale`) in `runtime/images/boxes.py` are another exception to the blanket rule that
all shared Pydantic models live in `contracts/`; document or deliberately resolve that boundary.

Keep thin tool factories and the existing responsibility folders. Avoid merging unrelated small
modules solely to reduce file count, or introducing a generic application framework. The main
navigation improvement is the README's concrete code reading path and clear document status.
Historical V0/V1 plans can remain for provenance, but should not be the starting point for a reviewer.

## Startup verification and limits

`uv sync --locked` succeeds. Both CLI configuration entrypoints compose successfully. The real
Agent Server passes the model-free schema check, and the paid smoke check completes with `pong`.
Both checks stop the server they start. Tracing was disabled for these checks.

The smoke test validates this environment's installation, graph assembly and (for the paid
check) API credentials/model response. It does not establish that a fresh machine can access
all geographic services, that every model ID is available to every account, or that a full
study will be accepted. The README states these prerequisites and failure modes instead of
promising unconditional startup. No full paid study or benchmark suite was run in this review.

## Final validation

- Locked dependency sync: passed.
- Ruff lint and formatting check over `src evals scripts tests`: passed.
- Strict `ty check`: passed.
- Full test suite: **844 passed** (793 before the review fixes).
- File/folder limits and public/private docstring AST audit: passed.
- README, review and EVALS local Markdown links: passed.
- CLI and eval configuration composition: passed.
- Real-server schema-only smoke check: passed.
- Real-server paid model smoke check: passed (`pong`).
- Missing `e2e` dataset CLI check: exits with an actionable error before model/corpus setup.

These changes are uncommitted. Existing unrelated workspace changes were preserved.
