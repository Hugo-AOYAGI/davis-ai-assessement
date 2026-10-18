# d09_outside_oap source review

Reviewed on 2026-10-17 by a Claude Sonnet source-review worker directly against the
supplied corpus, before any experiment. No agent output was used as expected data.
This sample has one manual source review; the planned two independent Opus drafts and
disagreement review were not performed.

Sources (1-based PDF page indices):

- `ressources/oap_91272_20210706.pdf` (corpus id `oap`, 36 pages), SHA-256
  `0c483af733f45a923ed8e212548fd23d835a0ce0307d98d54e28cf0fe9019cb1`.
- `ressources/plu_reglement_graphique_91272_20210706.pdf` (corpus id
  `plu_reglement_graphique`), SHA-256
  `9db34ecb0d0831c06860a88966f93fb1e3ed50cd2be6d1ae57ed6ab696d4b4c0`.

Reviewed pages and findings:

- OAP p.2 (sommaire): eight chapters. Plateau de Chevry (1), La Vallée (2 Vatonne,
  3 La gare de Gif, 4 Damiette (AURc), 5 Rougemonts, 6 hamlets), Le Plateau de Moulon
  (7 Moulon, 8 Joliot Curie). Joliot Curie sits under Moulon, not under La Vallée.
- OAP p.11: the Vallée index (islands to restructure: Vatonne, La gare - centre,
  Damiette, Rougemonts; old islands to preserve: three hamlets).
- OAP p.12 and p.13 (renders `oap_page12.png`, `oap_page13.png`): each chapter draws its
  own "Périmètre de l'OAP" on an aerial diagram (Vatonne: wooded slope above rue
  Vatonne; gare: station forecourt and rail strip). Neither is on Avenue du Général Leclerc.

Independent proof that no OAP perimeter covers the site: the zoning oracle
`evals/datasets/zoning/z11_vallee_ua.yaml` (parcel 91272000CA0005, zone UA). Its
`z11_vallee_ua.oracle.json` intersects the archived 2021 GPU layers with the parcel:
the PRESCRIPTION_SURF layer holds 10 OAP perimeters (TXT `OAP`, type 18), all with
intersection area 0 m2; the nearest is about 958 m from the parcel. The saved plan
crop `evals/fixtures/zoning/z11_vallee_ua.review.png` (viewed) shows the UA parcel with
no OAP perimeter pattern. The quote-less evidence on `plu_reglement_graphique` page 1
is that negative fact (a raster plan has no text layer).

Limitations: the statement "no OAP chapter applies" is a negative fact derived from the
GPU intersection and the plan crop, not from a quotable sentence. The raster crop is
registered approximately; the GPU vector intersection (distance about 958 m) is what
makes the conclusion safe.

## Review

Independent review (coordinator) objected to the fact "the OAP never mentions Avenue du
Général Leclerc": it rested only on a text-layer search, while the OAP maps are images
whose street names are not searchable. The fact was dropped from the item (now 5 facts)
and the text-search finding removed from the notes above. The perimeter conclusion
relies on the GPU intersection and the plan crop only. `evals.gt.check` and
`pages verify` were re-run after the change.

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d09_outside_oap.yaml
OK d09_outside_oap [doc, draft->verified] facts=5 must_flag=0 must_not=3

uv run python -m evals.gt.pages verify evals/datasets/doc/d09_outside_oap.yaml
3/3 quotes verified
```
