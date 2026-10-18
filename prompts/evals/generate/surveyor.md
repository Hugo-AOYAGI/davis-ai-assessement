# Surveyor ground-truth generation

## Lead

Build surveyor benchmark items according to `evals/README.md` and `evals/datasets/README.md`.
The existing `prompts/evals/tasks/surveyor.md` is the task under test; it is not
a data-generation prompt. Never run the surveyor to decide its expected answer,
copy its output into ground truth, or adjust an item to make a run pass.

Choose a trap from the planned cases or a reproducible random BAN address in
commune 91272. For random cases, require one nonempty `cad_parcelles` link and
commune certification. Record the seed and selection command. For traps, document
the independent manual justification rather than choosing the nearest parcel.
Delegate each selected case with the Sample instructions below. Keep independent
evidence separate from agent records. Review the evidence and run
`uv run python -m evals.gt.check <item path>` before marking an item verified.
Do not claim that schema validation establishes source correctness.

## Sample

Create one item at `evals/datasets/surveyor/<id>.yaml` using the common item
schema. Supply only the address (and a program if the case requires it) as input.

1. Use `evals.gt.site random --seed <seed> --n <count>` to select a linked BAN
   address, or `evals.gt.site ban <query>` to inspect an assigned address.
   The department CSV's `cad_parcelles` field is the parcel-selection oracle,
   independent of the agent's address geocoder and nearest-parcel search.
2. Query `evals.gt.site parcel <id> --save <fixture.geojson>` to confirm the
   linked parcel exists and save its geometry. Inspect address-point containment
   when selecting a straightforward case. Record cadastre `contenance` and the
   independently projected polygon area; use the area expectation with 2% tolerance.
3. Save the original BAN row and cadastre Feature alongside the polygon, with
   source URLs, retrieval time, BAN export hash, selection command and any review
   caveats. Do not infer road access from unregistered boundaries alone.
4. Add a critical `choice.parcel_ids` fact with `source: ban` for random items
   (`hand` for justified manual traps), plus `area_m2` with `source: cadastre`.
   Add neighbour or frontage assertions only if the independent evidence proves
   their meaning. Surveyor facts are deterministic; do not add judge assertions.
5. Set `built_by` honestly. Leave `status: draft` if evidence is incomplete or
   contradictory. Set `verified` only after parcel existence, source linkage,
   geometry and schema checks succeed. Preserve existing items and prompts.

Return the new item id, evidence paths, selection command, exact source values,
validation result and unresolved limitations. The experiment runner receives the
item only after this ground-truth work is complete.
