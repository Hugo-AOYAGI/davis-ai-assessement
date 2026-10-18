# e07_uga_housing evidence note

Reviewed 2026-10-17 before any experiment, from the documents, the cadastre, the BAN and
the archived 2021 GPU export; no agent output was used. Review method: Claude Sonnet source
inspection, with rendered images opened for the plan, the aerial photo and the strike-through
(`evals/fixtures/doc/d02_uga_height/page91.png`). The planned two independent Opus drafts
and human sign-off were not performed. All page numbers are 1-based PDF indices of
`plu_reglement` (printed number minus one).

## Deviation from the brief: the site is CA0128, not CA0160

The brief takes the parcel ids from `z12_uga`, which lists `91272000CA0160`. That parcel is
the allée de la Ferme Rose itself, not a building plot:

- Cadastre: CA0160 has contenance 1020 m2 and a polygon area of 1032.3 m2 for a perimeter of
  331 m. Shrunk inward by 4 m it keeps 3.5 m2, by 8 m nothing. It is a road-shaped strip
  with turning fillets.
- Aerial photo (IGN orthophoto, WMS, checked by eye): the strip is the paved allée; houses
  stand on the plots on both sides, each with a long garden running south toward the Yvette.
- BAN: `10 allée de la Ferme Rose` is a position of type `entrée` at (2.10573, 48.703195),
  `cad_parcelles` empty. The point falls inside CA0160 (the same relation as z12 records).
  The BAN points of 8, 12 and 18 allée de la Ferme Rose fall in or beside CA0127 (inside),
  CA0129 (0.1 m), CA0132 (0.3 m). The point of number 10 is 0.7 m from CA0128, and CA0128 is
  the plot between those of numbers 8 and 12. Command:
  `uv run python -m evals.gt.site near 2.10573 48.703195 40`.
- Zoning is unchanged by this: z12 (verified) puts CA0160 wholly in UGa, and the recomputed
  CA0128 is also wholly UGa. The z12 overlay facts (EBC, PPRi, zone humide absent) do not
  carry over, because CA0128 reaches into the PPRi.

The parcel choice is a hand inference (nearest plot to the address point, consistent with the
numbering of the street), not a BAN link; it is the same kind of trap as the CR0249 strip of
e01. The fact is `source: hand`, with the strip excluded explicitly.

## Parcel CA0128 computed values

Saved feature: API Carto `parcelle` query `code_insee=91272&section=CA&numero=0128`, retrieved
2026-10-17 (not saved as a repository fixture; this item may only write two files).

| Quantity | Value |
|---|---|
| Contenance | 978 m2 |
| Polygon area (Lambert-93) | 1001.12 m2 (the agent's `Site.area_m2` is computed from this polygon) |
| Shape | about 21 m wide, 75.5 m long, road edge on the north (the allée) |
| Zone, archived 2021 `ZONE_URBA` | UGa 100 %; N touches at 0 m2 |
| `PRESCRIPTION_SURF` | PPRi surface (`TXT` PPRI, `TYPEPSC` 02), 79.4 % of the plot, about 795 m2; nothing else |
| `PRESCRIPTION_LIN` | none |
| EBC, zone humide, emplacement reserve, OAP surface | none within 15 m |

Reproduce with `evals.gt.zones.oracle.oracle(<saved feature>, data/gpu_2021)`, the same function
that built the z-items. Source hashes: see `evals/fixtures/zoning/z12_uga.oracle.json`
(`ZONE_URBA` `31ab4368...`, `PRESCRIPTION_SURF` `0c9fea94...`; the same archive files).
A diagnostic overlay of the plot on the plan crop was rendered with the registration of
`evals/gt/zones/raster.py` and opened: the dashed PPRi boundary of the raster plan crosses the
plot close to its north end (the road side), leaving the southern part inside the PPRi, in line
with the GPU polygon. Registration is approximate, so
no fraction is read from pixels, and the PPRi item is not marked critical.

`site area`: expected 1001.12 m2 with 2 % tolerance (the contenance, 978 m2, is 2.3 % lower and
is not the geometry the agent computes).

## Regulation facts (UG, sector UGa)

| Fact | Page | Notes |
|---|---|---|
| UGa footprint 15 % of the plot (annex constructions 4 %); general UG is 30 % | 90 | d02, critical; the general 30 % explicitly excludes UGa |
| UGa height 7 m at the acrotère; 10 m struck through | 91 | d02 plus rendered page, critical; general UG heights (7 m eaves, 10 m ridge) exclude UGa |
| No storey limit for UGa | 91-92 | R+2 appears only for UGg; expected `null` |
| Road: at the alignment or set back (5 m only along avenue du Général Leclerc and route du Val de Courcelle) | 86 | the allée is not named, so on-limit is allowed |
| Side and rear (limites séparatives): setback L=H, minimum 8 m with views; L=H/2, minimum 4 m without views; building on one or two lateral limits allowed | 88 | UGa and UGd share this rule; rear on-limit is not scored (the text lists lateral limits only) |
| Parking: 2 places per dwelling | 94 | d02 |
| Green space: UG13 asks one tall tree per 100 m2 and 10 % of the plot as common green space only for operations over one hectare; no numeric minimum for a single house | 97 | expected `min_green_ratio` null |
| Housing is the purpose of UG; UG1 does not forbid it, UG2 does not condition it | 80-81 | verdict accepts permitted or conditional (PPRi) |
| PPRi is a public easement whose provisions sit in annex 6.3 of the PLU | 6, 81 | outside the three corpus documents: must be flagged |
| OAP: the OAP document has no chapter for the Val de Courcelle / UGa; no GPU OAP surface touches the plot | OAP p2 | `oap_applicable` false |

The 13 quotes in the YAML were checked with `evals.gt.pages verify` (13/13 at 1.00) and
`evals.gt.check` loads the item as verified.

## Derived geometry and omitted oracles

- Footprint cap: 0.15 x 1001.12 = 150.17 m2. Checked that the setback ground footprint exceeds
  the cap whatever the edge labelling: with a 4 m setback on every edge it is 333 m2, with 0 m
  on the road edge and 4 m elsewhere 678 m2. The `largest` bound is therefore capped, so
  `envelope.bounds[name=largest].buildings.footprint_area_m2` = 150.17 m2 for one building.
  The `windows` bound and the proposal depend on how the edges are labelled and are not scored
  with a fixed value.
- No minimum green area: `min_green_area_m2` is null because no ratio is set.
- No proposal volume is asserted (height at most 7 m, windows, cut and shares are the
  architect's choices); the harness recomputes the submitted proposal.
- Not verified here: that the road edge faces the allée and that CA0160 is declared public land
  (the gate labels edges); whether the plot already carries a house (the aerial photo suggests
  so; the program is read as new construction on the plot); the rear on-limit rule.

## Limits

One reviewer only. The parcel choice and the PPRi coverage are my computations from the same
independent sources as the z-items, not an existing verified component item; z12 and d02 cover
the zone, the height and the footprint. The `must_flag` on the strike-through assumes the
agent can see the page image; if a run reads only the text layer it is expected to raise the
two-figure reading as an open point.
