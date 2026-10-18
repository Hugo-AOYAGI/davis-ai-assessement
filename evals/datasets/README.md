# Evaluation datasets

The surveyor, zoning and document datasets each contain 20 source-checked items;
the end-to-end dataset contains 10. Generators follow the Lead/Sample
instructions in `prompts/evals/generate/`; expected answers were established
before experiments, without copying agent-under-test outputs.

## Document

The [case index](../cases/doc.yaml) holds 11 traps and 9 zone × program cases.
The traps are Vallée UA vs Chevry UA, the struck-through UGa height, AURc's
references to UR, the Titre I parking cap, UMG public-interest exceptions, green
roofs (UMG 13 vs lexique), the Joliot Curie OAP, a site outside every OAP, the
PPRi deferred to a document outside the corpus, and repealed articles 5 and 14.
The grid cases are Chevry UH, Chevry UA, UM4, UM5a, UGd, UGc, UCa, UHe, UXc
offices and N, the negative case. Each input copies the playbook's aim and
topics for its label; the zone and legend items come from the zoning items.

One Sonnet worker per item read the corpus pages, inspected page images for
strike-through and tables, and verified every quote with `evals.gt.pages verify`.
Four independent Sonnet reviewers then re-read every critical statement and
`must_not` against the pages. Their fixes, mostly the "opérations d'ensemble"
parking rules and must-nots a correct answer could trip, were applied; each
evidence note under `evals/fixtures/doc/<id>/` ends with a "Review" section.
The planned two independent Opus drafts were not run.

## End to end

The [case index](../cases/e2e.yaml) lists e01–e10. Each item takes its parcel,
zone and rules from component items (`from_items`), reads any missing figure in
the corpus, and scores layout-independent values only: parcels, zone, OAP
applicability, cited envelope parameters, site area and derived green areas.
No proposal volume is asserted. Every key resolves against the current
`VerifiedStudy` contracts. Known limits:

- e07 uses parcel CA0128, the house plot; the BAN point of its address falls in
  the private lane CA0160, which `z12_uga` keeps as its zoning input.
- e08 uses the Vallée UH site of `z03_ebc`; none of the UH zoning items is in
  Chevry UH (UHa / UHb).
- e10 expects a `prohibited` verdict. The current gate permits a wholly prohibited
  study without an envelope; historical runs predate this correction.

The end-to-end items had one source review each, without an independent reviewer.

## Surveyor

The [case index](../cases/surveyor.yaml) combines ten trap slots and ten random
addresses. Detailed selection records remain in
[surveyor_random.yaml](../cases/surveyor_random.yaml) and
[surveyor_traps.yaml](../cases/surveyor_traps.yaml).

The traps cover the reference strip, a corner, a two-parcel site, an entrance
point outside its parcel, hamlet context, identical addresses in neighbouring
communes, cadastral enclosure, a house-number suffix, several entrances to one
campus parcel and a deliberately unknown address. Legal landlocking is a coverage
gap: cadastral enclosure does not prove the absence of legal access or easements.

Random cases are selected with recorded seeds and source-quality checks, across
4 Vallée, 3 Chevry and 3 Moulon addresses. This is conditional stratified sampling,
not a uniform commune sample. Two commune-certified entrance points lie less than
one metre outside their explicitly linked parcels; the snapshots disclose this.

Original BAN rows, cadastral Features, projected geometry measurements, source
URLs/hashes and maps are saved under `evals/fixtures/surveyor/`. A second worker
rechecked the trap parcel sets, unions, areas and distinguishing source evidence.
The original reference's parcel selection remains an inherited manual adjudication;
its geometry and strip distances were independently rechecked.

The unknown-address item has `expected_refusal` rather than fictitious parcel
facts. It requires a real geocoder reply followed by an explicit refusal, no
parcel submission, no site artifact and no runtime error. A crash, silent exit
or textual service failure cannot pass. Ordinary missing artifacts still fail.
Lookup completion is checked; semantic relevance of a rewritten query is not.

## Zoning

The [case index](../cases/zoning.yaml) contains ten traps and ten zone-spread
cases. In total, their expected answers cover 18 zone/sub-sector codes, including
the two alternatives for the boundary-crossing parcel.

Traps cover OAP, a UCa/UD boundary, partial EBC, PPRi, reserved land, protected
retail frontage, natural zoning, Chevry UA, UXc and a source-version disagreement.
The remaining cases cover Vallée UA, UGa, UGd, UGc, AURc, UM4, UM5a, UME, UHe and UEc.
The version case supplies an exact vacant parcel and a location description,
not an invented postal address: its expected 2021 zone is UM5, while the saved
2026 comparator places it in UM5b.

Full current cadastral polygons are intersected with the archived
`91272_PLU_20210706` zone, surface-prescription and linear-prescription layers.
Current online zoning never supplies expected answers. Each new item retains
raw cadastral/BAN evidence, hashes, whole-parcel oracle calculations, an original
plan crop and a separate annotated diagnostic crop under `evals/fixtures/zoning/`.
Recomputing the oracle requires the local archived GPU files under `data/gpu_2021/`.

A separate worker recomputed all 19 new parcels against the archived layers and
checked the sources. Another reviewed 15 original/annotated image pairs, in
addition to five other cases reviewed separately. See
[independent visual review](../fixtures/zoning/INDEPENDENT_VISUAL_REVIEW.md).
Registration is approximate; tiny intersections can be vector-supported without
being visually resolvable. The source notes distinguish these forms of evidence.

`ZoneFindings` has no citation fields, so zoning grounded accuracy currently
equals answer accuracy. The snapshots support source review, not a claim that
the scorer verifies raster regions. The UA cases check explicit wrong-sector
claims, but omitting a sector can still pass. Boundary/partial-coverage flags are
reported separately by the judge; missing flags do not currently fail the item.

## Verification and use

`verified` means checked against retained sources and the schema by Codex workers;
it does not mean human sign-off or complete coverage of all planning questions.
The items define expected answers independently of measured agent results.
Historical experiments are published in `handoff/evaluation.html`; the dataset
construction itself did not run the agent to establish those answers.

```powershell
$env:PYTHONUTF8 = '1'
uv run python -m evals.gt.cases list surveyor
uv run python -m evals.gt.cases list zoning
uv run python -m evals.gt.zones.audit
```

To run paid experiments, with the source corpus and credentials available:

```powershell
uv run python -m evals.run eval.dataset=surveyor
uv run python -m evals.run eval.dataset=zoning
```

These use the configured Sonnet judge when assertions require judging, and
Phoenix by default. The two commands must use distinct Hydra run directories
if launched simultaneously within the same second.
