# Independent review of fifteen zoning plan crops

Reviewed by a separate Codex worker on 2026-10-17. This is an agent source review,
not human sign-off. No experiments or model API calls were run. Only this note
was written; datasets, original sources, helpers and rendered images were not
modified by this reviewer.

For every case below, **both named PNGs were actually opened using
`tools.view_image`**: the unaltered source crop (`.plan.png`) and the diagnostic
crop (`.review.png`). The source legend image at
`data/scratch/zoning/legend.png` was also opened. The JSON oracle rows were read
for context after looking at the images; they are not substituted for visual
observations. Current inputs were read from `evals/cases/zoning.yaml`.

Source plan: `ressources/plu_reglement_graphique_91272_20210706.pdf`, page 1.
SHA-256: `9db34ecb0d0831c06860a88966f93fb1e3ed50cd2be6d1ae57ed6ab696d4b4c0`.
The diagnostic draws the selected parcel in red and archived zone boundaries
in blue. Those added blue lines are not source overlay markings. The registration
is approximate: generally close agreement with source black zone boundaries was
visible, but this cannot establish exact intersections at a parcel corner or
thin strip. Percentages come from the archived 2021 vector layer, not pixel
measurements.

All image links below are relative to this note's directory. Each pair is the
actual source and annotated image inspected.

| Case and inspected images | Source-image observations and alignment assessment | What remains dependent on vector evidence |
|---|---|---|
| z05: [source](z05_emplacement_reserve.plan.png), [annotated](z05_emplacement_reserve.review.png) | UH and UHc labels are legible. The red narrow parcel is in the UH block south of the UHc boundary, against its southern edge. Diagnostic boundaries broadly follow the source divisions. A narrow blue-marked strip runs along the southern zone edge near the target. | The crosshatching is too small at the parcel to independently confirm its exact extent. The claimed 8.06% reservation comes from archived `PRESCRIPTION_SURF`, not this image. I do not claim the crop visually proves that percentage. |
| z06: [source](z06_retail_frontage.plan.png), [annotated](z06_retail_frontage.review.png) | UAa is legible above the central commercial street. The red target is on its north side, within the UAa block. Yellow square/dash commercial-frontage marking is clearly visible along that street and reaches the target frontage; it matches the legend's commerce symbol. Blue zone traces track the UAa/UAb/UAd divisions plausibly. | The precise 14.47 m intersection is a vector-line result. The red parcel edge and nearby source typography prevent pixel-level verification of its endpoints. |
| z07: [source](z07_natural_zone.plan.png), [annotated](z07_natural_zone.review.png) | The target is tiny, north-east of the central Nc pocket, in the continuous green N area. The N label and surrounding Nc, UR and UL divisions are clear. Diagnostic N/UR boundaries fit the source broadly. Blue reservation symbols and the circled z marker occur immediately beside the target. | The target is too small to see the detailed ER boundary reliably. The 58.19% turning-area reservation is supported by the archived polygon; it is not independently measured or fully resolved visually here. |
| z09: [source](z09_uxc.plan.png), [annotated](z09_uxc.review.png) | UXc is legible, with UGe immediately to the west and UR to the east. The red rectangle is in the small UXc division, rather than the adjacent UGe area. Blue traces track the small source zone boundary reasonably closely. | An approximately 0.02% landscape-feature intersection in the oracle is too small to identify in the raster. No visual confirmation of that sliver is claimed, and an empty `present` list must not be read as proof that every possible source layer is absent. |
| z10: [source](z10_version_disagreement.plan.png), [annotated](z10_version_disagreement.review.png) | The actual 2021 source visibly says **UM5**, not UM5b. The red triangular parcel lies within that pink zone. UM3 is separately labelled above the horizontal boundary. The magenta dotted outer OAP perimeter is visible east and south of the selected parcel; blue zone traces broadly match the source. | The separately saved `.current2026.json` was read only as a comparator. Its response contains both UM5 and UM5b Features; independently intersecting those saved geometries with the saved parcel gives zero area in current UM5 and effectively 100% in current UM5b. No 2026 image was used to reinterpret the 2021 expected label. |
| z11: [source](z11_vallee_ua.plan.png), [annotated](z11_vallee_ua.review.png) | UA is legible in the small dark red area on the west edge of the mapped commune. The tiny red target sits in that dark red UA block, close to its boundary with the pink UC area. The diagnostic preserves that distinction. | The tiny target and proximity to UC mean exact full-parcel coverage cannot be checked from these pixels alone; the archived vector intersection supplies that fact. |
| z12: [source](z12_uga.plan.png), [annotated](z12_uga.review.png) | UGa is clearly labelled in orange, below UC and west of the purple UXc zone. The irregular red target follows an internal strip within UGa and approaches its eastern edge. Diagnostic zone traces track those source divisions plausibly. | Detailed containment along the narrow irregular target edge needs vector geometry; no exact boundary-area fraction is inferred from the crop. |
| z13: [source](z13_ugd.plan.png), [annotated](z13_ugd.review.png) | UGd is clearly legible in the orange enclave below UCa. The red parcel lies in its western portion. The blue enclave boundary closely follows the black source outline. | No fine parcel-area percentage or complete overlay absence is established solely from the image. |
| z14: [source](z14_ugc.plan.png), [annotated](z14_ugc.review.png) | UGc is clearly legible in the small orange enclave south of ULc and west of UXb. The red parcel outline lies within that enclave. The diagnostic matches the surrounding zone outlines plausibly. | Exact edge containment and negative overlay tests remain vector checks. |
| z15: [source](z15_aurc.plan.png), [annotated](z15_aurc.review.png) | AURc is legible over the white/orange-hatched block west of URb. The red parcel is within that AURc block. A magenta dotted OAP perimeter surrounds the block and is clearly visible in the unaltered source. Blue traces preserve the distinction from URb and neighboring UH. | Background zone hatching must not be mistaken for an unrelated mapped overlay. Fine overlay intersections and exact full coverage remain vector checks. |
| z16: [source](z16_um4.plan.png), [annotated](z16_um4.review.png) | UM4 is legible lower left, UM5a above the road, and UME west of the vertical division. The red rectangular parcel is south of the UM5a boundary, in the continuous UM4 region. Blue boundaries follow the road/zone divisions reasonably well. | The visible magenta boundary east of this parcel is the nearby UMG-sector perimeter. It does not by itself prove this target's broader Moulon OAP membership; that membership comes from the archived OAP polygon and wider context. |
| z17: [source](z17_um5a.plan.png), [annotated](z17_um5a.review.png) | UM5a, including the lower-case suffix, is directly legible over the grey building area. The red parcel is within the small source-outlined UM5a area north of the road. Added blue lines are slightly offset from source black edges at this scale but preserve the same zone placement. | Exact boundary coincidence is not established. As in z16, the nearby magenta line east of the target is not independently sufficient proof of broader Moulon OAP membership. |
| z18: [source](z18_ume.plan.png), [annotated](z18_ume.review.png) | UME is clearly labelled in mint green. The red U-shaped target occupies the lower green block, north of the road separating it from pink UM3. The source magenta dotted perimeter is visible at the western outer edge, outside the target. Blue traces follow the UME/UM3 division plausibly. | The irregular target's exact polygon coverage is a vector result. No current-version zoning is substituted for this archived UME label. |
| z19: [source](z19_uhe.plan.png), [annotated](z19_uhe.review.png) | UHe is clearly legible within a purple diagonal-hatched area. The narrow red parcel lies within that hatching. The source legend identifies this purple hatching as the sanitary-prescription perimeter; the different dashed recommendation perimeter is also visible farther out. Blue zone traces follow the main source boundaries plausibly. | Exact 100% sanitary coverage is vector-based, though presence of the prescription pattern at the target is directly visible. |
| z20: [source](z20_uec.plan.png), [annotated](z20_uec.review.png) | UEc is legible in the central/north-west brown residential block, with UEa south-west and UEb east. The small red parcel lies within UEc. A magenta dotted perimeter is visible around the wider district, including its northern and southern outer edges. Blue outlines preserve the UEc/UEa/UEb divisions. | The archive also contains an `Ensembles batis coherents` surface record. I do not infer a specific scored legend category for it merely from the patterned brown background. Exact OAP full coverage remains a vector result. |

No gross contradiction between the fifteen expected archived zone labels and
their source-plan placement was found. The review does **not** turn unresolved
tiny ER patterns into visually confirmed intersections, establish legal rights,
or certify every negative overlay assertion from absence of a visible symbol.
Source hashes and whole-polygon intersections in the independent archived
layers provide the separate evidence for those numerical/negative claims.

The owner was notified immediately of the small-ER visibility limits (z05/z07),
the unresolvable landscape sliver (z09), and the distinction between the visible
nearby UMG perimeter and broader Moulon OAP membership (z16/z17). None required
changing a dataset value based on this review.
