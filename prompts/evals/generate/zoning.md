# Generate zoning ground truth

## Lead

Read `evals/README.md` and `evals/datasets/README.md`, `evals/harness/items.py` and existing verified
items. Select one trap or a site that improves coverage across zones. Supply a
parcel selection established independently from zoning-agent output. Delegate a
Sample task containing the case, desired item id, cadastral fixture, archived GPU
location and corpus plan. Keep each Sample independent of agent runs. Review its
provenance and schema validation before marking the item verified. Do not run an
experiment until its expected answers are frozen.

## Sample

Create one YAML under `evals/datasets/zoning/` using the zoning input schema:
address, parcel_ids and program. Read only independent sources for expected answers.

1. Check the saved cadastral polygon and project it to EPSG:2154. Intersect the
   complete polygon with `91272_ZONE_URBA_20210706.shp` and
   `91272_PRESCRIPTION_SURF_20210706.shp`. Check linear prescriptions too where
   relevant. `uv run python -m evals.gt.zones.oracle` reproduces the reference case;
   `--parcel` and `--archive` choose other local inputs.
2. Use the archived `91272_PLU_20210706` export, never current online zoning. Save
   source names, hashes, intersected records, area fractions and boundary distances
   in a provenance note. Check the raster corpus plan and its legend visually;
   use labels exactly as printed. Generic GPU OAP labels need geometry or the OAP
   document to identify their sectors. Do not infer an OAP name from its generic label.
3. Score `zone` as a critical fact with `source: gpu_2021`; preserve the raster
   evidence on `plu_reglement_graphique`, PDF page 1, in the provenance note.
   `ZoneFindings` currently has no citation fields, so attaching item `evidence`
   would make every answer fail grounded scoring. Omit that field until the
   harness explicitly evaluates its image region; disclose this scoring limit.
   Add only verified overlay expectations. Mark zone and overlay facts critical,
   so a missed protection cannot pass the item merely because its zone is correct.
   Preserve disagreement or boundary uncertainty in `must_flag`; do not choose the
   most convenient zone. A partial overlap is not a whole-parcel assertion.
4. An absence must be checked against the appropriate layer and raster legend.
   An omitted, unavailable or generically encoded layer is not proof of absence.
   Do not add unverified negatives to make the item appear comprehensive.
5. Validate with `evals.harness.items.load_item`. Keep an item draft if verification
   is incomplete. Report the files and unresolved evidence gaps to the Lead.
   For the full suite, use `evals/cases/zoning.yaml`: ten traps and ten coverage
   cases. Preserve full parcel sources and the snapshots, and run
   `uv run python -m evals.gt.zones.audit` before handing them back. A current GPU
   snapshot may demonstrate a version-disagreement trap only as a separately
   labelled comparator; it must never replace the archived expected-answer oracle.

Never copy agent responses, run records or experiment scores into expected facts.
Do not change expectations to make an experiment pass.
