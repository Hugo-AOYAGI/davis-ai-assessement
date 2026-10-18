# Zoning dataset: sources, coverage and limits

The suite contains 20 verified items: 10 traps (`z01`–`z10`) and 10 zone/sub-sector
coverage cases (`z11`–`z20`). Expected answers were frozen from independent source
geometry and raster review, without agent experiments or model API calls.

## Retained evidence and reproduction

Each item has these files in this directory:

- `.cadastre.json`: the complete original cadastral Feature, wrapped as a
  FeatureCollection. No polygon simplification, clipping or proxy point is used.
- `.sources.json`: original cadastral source and original BAN row, source URLs,
  hashes, and the precise address/parcel relationship. `z01` preserves the older
  already-shipped API Carto fixture and does not invent its retrieval date.
- `.oracle.json`: every archived zone, surface and linear prescription record;
  full-parcel intersection areas, fractions, lengths and distances in Lambert-93;
  source hashes; raster review references and image hashes. All records are
  preserved, including tiny overlaps and zero-area boundary touches.
- `.plan.png`: unaltered rendering of the 2021 plan crop, PDF page 1.
- `.review.png`: diagnostic rendering with the complete parcel boundary in red
  and archived zoning boundaries in blue. Added blue outlines are not source
  prescription symbols. The original plan must be read alongside the diagnostic.

Run `uv run python -m evals.gt.zones.audit` to reload every item and independently
recompute its saved metrics and expected zone/overlay assertions. All 20 items
pass. The raw archived layers must exist at `data/gpu_2021/`, as documented in
`evals/README.md`; they are locally cached and ignored by Git. Nothing falls back
to a live zoning oracle. The retained original parcel features allow rerunning
without downloading current cadastre or BAN data.

`uv run python -m evals.gt.zones.raster` reproduces all crops. The actual affine
registration coefficients, origin, normalized width, sampling and fitting method
are in `evals/gt/zones/registration.json`. Registration was fitted globally to
82,184 source-zone sample points on a 12 m grid across all 152 archived polygons,
after initialization in UMG. The fit score is color-fill agreement, not surveyed
positional accuracy. A provisional UMG-only transform was rejected after visible
drift elsewhere; the committed crops use the global affine registration. Exact
areas and distances always come from cadastral and GPU geometries, never pixels.

An independent worker recomputed all 530 record metrics for each of the 19 new
sites and checked source hashes, every zone expectation, the three negative
overlay categories, and the current-version comparison. It found no mismatch.
A separate visual review actually opened both source and diagnostic images for
15 cases; see [INDEPENDENT_VISUAL_REVIEW.md](INDEPENDENT_VISUAL_REVIEW.md).

## Traps and geometric coverage

| Item | What is established independently |
| --- | --- |
| z01 | CR0247 is 100% UMG and lies in two nested generic OAP surfaces. OAP names are not inferred from generic GPU labels. |
| z02 | BI0093 is 75.3192% UCa and 24.6807% UD; both choices are accepted and the split must be raised. No UH overlap exists in the oracle. |
| z03 | CO0051 is UH, with EBC covering about 38.63%; partial coverage must be raised. |
| z04 | BK0007 is UH and wholly inside the PPRi surface. |
| z05 | BE0321 is UH; an emplacement réservé covers about 8.06%, not the whole parcel. |
| z06 | CM0031 is UAa and intersects 14.47 m of protected commercial frontage. |
| z07 | CC0193 is N; a turning-area reservation covers about 58.19% of its 129.3 m². Existing address presence is not an admissibility oracle. |
| z08 | AH0198 is UA in Chevry, not Vallée. |
| z09 | CC0080 is UXc; the sector suffix matters. An extremely small other landscape intersection remains recorded but is not scored or claimed visually confirmed. |
| z10 | Vacant ZQ0134 is UM5 under the archived 2021 plan and effectively 100% UM5b under the separately saved 2026 comparator. |

The ten remaining cases cover Vallée UA, UGa, UGd, UGc, AURc, UM4, UM5a, UME,
UHe and UEc. Together the suite exercises 18 distinct zone labels, counting
both sides of the boundary case. Programs are supplied independently and do not
come from a surveyor or another agent's output.

The reference parcel for `z10` has no BAN address point inside it. Its input is
explicitly a parcel location description and a nearby BAN landmark, not a claim
that the vacant parcel owns that postal address. The selected parcel is given
directly to the zoning component. This is not a surveyor address-resolution item.

## Raster checks and limits

The owner actually opened both `.plan.png` and `.review.png` for `z01`, `z02`,
`z03`, `z04` and `z08` and read the original plan legend. UMG and its nearby NF
EBC separation, the UCa/UD split, partial EBC at the UH edge, the PPRi blue dashed
perimeter, and Chevry UA with the district's outer OAP markings are compatible
with the independent intersections. All other pairs were opened by the separate
visual reviewer named in its note. This is an agent source review, not human
sign-off and not a survey-quality georeferencing claim.

Thin reservation strips in `z05` and the tiny target in `z07` are not visually
resolvable enough to prove the exact percentages. Those facts rest on the
archived vector records. Similarly, the nearby magenta UMG boundary in `z16` and
`z17` alone does not prove membership of the wider Moulon OAP; the complete
archived OAP surface establishes it. Fine geometry is not inferred from labels
or a conveniently placed point. The source checker found no gross raster/vector
zone contradiction requiring a draft or alternate expectation.

Absences are scored only for EBC, PPRi and wetlands, after checking every relevant
surface record over the complete parcel and a positive separation distance
greater than 2 m. An empty `present` list does not mean all overlays are absent.
Other heritage layers and unavailable legend mappings are unscored, not erased.
Exact legend labels are used; generic CNIG category text is not copied as a
replacement for the printed legend wording.

The current comparator is saved separately in
`z10_version_disagreement.current2026.json`, including its request URL and raw
response. It contains UM5 and UM5b Features, but intersection gives zero area
in current UM5 and effectively 100% in UM5b. Its `idurba` is
`91272_PLU_20260408`. The expected answer uses only `91272_PLU_20210706`.

## Scoring limits

Both zone and overlay facts are critical in every item: missing a verified
protection makes the item fail. `must_flag` coverage remains a separate metric
under the existing harness; the boundary item accepts either intersecting zone
while requiring the split to be reported through that metric.

`ZoneFindings` carries no citations, so the current harness cannot measure
citation grounding for this component. Evidence remains in these provenance
files and YAML `evidence` is omitted; reported grounded accuracy consequently
equals answer accuracy (`cited: null`). This does not certify which crop the
model inspected. No output contract was changed for this dataset task.

For `z08` and `z11`, `must_not` detects an explicitly wrong district in the
rationale. A district omitted entirely can still pass because the output has no
typed district field. Partial protections have `must_flag` assertions; the exact
fractions are documented here and in the oracle, not imposed as numeric output
fields the component cannot represent.
