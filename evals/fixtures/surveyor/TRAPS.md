# Surveyor trap-source review

Prepared on 2026-10-17 without running the surveyor, experiments or model API calls.
Geographic source downloads were used: department BAN export, API Carto cadastral
sections and two small OpenStreetMap map extracts. The original `s01` and `s02`
items were preserved. The random-sample worker owns `s02` and `s11`–`s19`.

`evals/cases/surveyor_traps.yaml` records the ten trap slots. Each new positive
case has `sources.json` (raw BAN row, related address rows, original cadastral
Features, query URLs/timestamps, BAN export hash and geometry measurements),
`site.geojson` (WGS84 union polygon), and `map.png`. The two street-context cases
also preserve the original OSM XML and its hash. All eight new maps were actually
inspected using `tools.view_image`; this is Codex review, not human sign-off.

| Item | Independently supported differentiator |
|---|---|
| s01 | Inherited manual reference: CR0249 strip is 1.82 m from BAN point; selected CR0247 is 2.53 m away. Added audit checks parcel existence/geometry; BAN has no parcel link and does not independently re-establish the original manual site adjudication. |
| s03 | BK0330 is at the corner of Chemin des Avelines and Rue de la Fontaine. OSM centerlines are 3.8 m and 2.7 m away; cadastral plot and both streets inspected visually. |
| s04 | Certified BAN address explicitly links adjoining BM0417 and BM0419; union is one Polygon, 1390.05 m². Nearest-only selection loses the second parcel. |
| s05 | 13 Allée des Troènes: certified entrance point is outside all nearby cadastre, 12.69 m from its nearest/linked CO0036 and 1.72 m from the OSM street centerline. |
| s06 | BAN `nom_ld` explicitly says Hameau de la Clairière; number 118 links AK0548. Tests a numbered hamlet address, not an invented hamlet classification. |
| s07 | Exact number/street 5 Rue de la Fontaine occurs in both Gif-sur-Yvette and neighboring Saint-Aubin in the department export. Only Gif's row is the requested commune and links BK0099. |
| s08 | BK0239 is surrounded by registered cadastral polygons; complete boundary falls within 0.5 m buffers of neighbors. Tests the selected site and an evidenced neighbor; legal landlocking is unproved. |
| s09 | 2, 2bis and 2ter Chemin des Grands Prés are separate certified rows linked to CK0119, CK0120 and CK0122. Explicitly excludes the two incorrect suffix choices. |
| s10 | CP0220 is shared by BAN addresses on Rue Francis Perrin, Rue Pierre Potier and Route 128. Tests whole-parcel selection in Moulon despite multiple entrances/streets. |
| s20 | Deliberately synthetic `999999 Rue des Licornes Inexistantes` has neither street nor house number in all 5775 commune BAN rows. Uses the expected-refusal contract, no fabricated parcel fact. |

The ten slots include a **cadastral-enclosure proxy instead of a verified legally
landlocked property**. Cadastral registration does not identify road ownership or
access easements. Roadpoint and corner contexts are geometrically supported but
do not establish legal public frontage. Also, the new site traps do not claim to
cover every e01–e10 PLU zone; zoning was not inferred from rough geographic sector
heuristics. These remain explicit coverage limitations.

A preliminary Rougemonts candidate was discarded before finalizing: the BAN
point was inside another cadastral property and its linked L-shaped parcel
created an unresolved site-selection question. It is absent from the final set.

Source selection scanned 33 commune cadastral sections (6938 Features) and 1750
BAN-linked rows. `generate_traps.py.txt` preserves the one-off artifact-writing
script for provenance, not an automatically reviewed dataset-building tool.
Saved final review records are authoritative; regenerating requires fresh review
before assigning verified status.

Validation completed with UTF-8 enabled in PowerShell:

```powershell
$env:PYTHONUTF8 = '1'
uv run python -c "from pathlib import Path; from evals.gt.check import main; raise SystemExit(main([str(p) for p in sorted(Path('evals/datasets/surveyor').glob('*.yaml'))]))"
```

All 20 surveyor items loaded as verified. This checks schema; the independent
source/geometry and visual checks above establish the eight new positive labels.
No experiments were run during generation.
