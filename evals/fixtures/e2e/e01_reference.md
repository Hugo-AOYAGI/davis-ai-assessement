# Reference study oracle

Reviewed before launching the end-to-end experiment on 2026-10-17. Expectations
were assembled from source documents and component ground truth, never from the
output being evaluated. Review method: Codex source inspection; the planned two
independent Opus drafts and human sign-off were not performed for this smoke set.

- Parcel: existing verified `s01_joliot_curie` chooses CR0247 and rejects the
  CR0249 strip. The saved cadastral feature is
  `tests/adapters/geo/fixtures/cadastre_CR0247.json`.
- Zone and OAP applicability: `z01_joliot_curie`; reproducible archived-2021
  full-polygon intersections and source hashes are documented in
  `evals/gt/provenance/z01_joliot_curie.md`.
- Regulation PDF p320 identifies student housing as an intended UMG use.
  PDF p326 sets housing height to 20 m and R+5, and article 9 leaves footprint
  unregulated. These are PLU limits; the OAP can further shape the proposal.
- Regulation PDF p331 requires 20% green space for this housing program.
  PDF p330 excludes vegetated roofs from that green-space calculation.
- The cadastral measured site area is approximately 5951.5–5951.6 m², depending
  on coordinate precision. The expected area is 5951.6 m² with 2% tolerance;
  the expected minimum green area is 5951.6 × 0.20 = 1190.32 m².
- Regulation PDF pp5–6 states the Titre I parking cap and its categories;
  UMG parking begins on p327. The assertion requires reconciliation and
  applicability conditions, not automatic application to every residence.
- OAP PDF pp33–36 contains the Joliot Curie orientations, including the
  objective of average R+4 for housing. This is distinct from the PLU R+5 limit.

All page numbers are 1-based PDF indices. The three explicit YAML quotes were
checked with `evals.gt.pages verify` and matched at 1.00.

No fixed proposal volume is asserted: the requested two buildings allow several
cuts, shares, facing-window choices and heights. The harness checks the submitted
proposal by deterministic recomputation, while this item independently scores
site area, green area and selected regulatory parameters. It is not a complete
oracle for every envelope rule or the optimal achievable building volume.
