# Workflow facts

This site illustrates the maintained repository workflow, with saved images and a historical
recorded demo. It does not execute the agent. Consult root `README.md`, `CLAUDE.md` and
`prompts/playbooks/study.md` for runnable instructions and current contracts.

## Data and sequence

Ingestion builds a text corpus from the three bundled PDFs and fits a ground-to-pixel
transform for the raster plan using the official commune boundary. The registration file
records its source, date, image dimensions, CRS and fit errors.

The surveyor chooses parcels and code builds their geometry. The zoning analyst uses
`plan_site` to see their outline on the georeferenced plan, then reads its labels/legend.
The outline has registration uncertainty; it does not automatically determine legal zoning.
Document tasks extract cited rules, OAP orientations and destinations after zoning completes.
The architect translates notes into rules and layout; the orchestrator decides interpretations
and submits the final study. Document tasks may run concurrently; the preceding dependencies
remain sequential.

## Validation

Artifacts are typed JSON, not merely free-text specialist summaries. The final gate requires
site, zone and notes; it reconciles zone/overlays, checks note artifact labels, preserves
open questions, validates source quotes and envelope inputs, recomputes geometry, and saves
evidence crops. Failed submissions return field errors and can be revised by path edits.

When every proposed building use is prohibited, the cited negative study has no envelope.
Mixed programs include only eligible buildings in the envelope while retaining all verdicts.
Other studies require an architect artifact. Geometry checks do not establish that cited
numbers correctly interpret the law; quote checks establish source-text support, not meaning.
Raster crops are inspectable evidence, not automatically verified diagrams.

## Geometry and recorded examples

Setbacks vary with height. The solver computes slices, two rule-based bounds and a simplified
multi-building proposal. Under footprint/green-area caps, it conservatively trims contained
polygons and recomputes slices, keeping geometry, area and volume coherent. It does not
optimize every possible arrangement. The historical recording predates this cap correction
and the all-prohibited branch; its displayed figures are recorded examples, not new results.

Parking capacity, dwelling yield, ownership and comprehensive legal compliance are outside
the implemented checks. Storey limits are reported separately from geometric volume.
Standard study-topic minimums are enforced from shared configuration. Arbitrary focused
labels and building-specific topic completeness remain model-declared.

## Provenance

Final images and the video are retained in `assets/`; font licenses accompany their files.
`assets/img/PROVENANCE.md` records historical capture sources and image processing. Paths
to raw recordings/scratch outputs are provenance, not serving dependencies. The curated
bundle contains everything required to serve this site without the authoring repository.
