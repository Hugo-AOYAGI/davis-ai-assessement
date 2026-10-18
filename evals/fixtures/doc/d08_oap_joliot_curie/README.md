# d08_oap_joliot_curie source review

Reviewed on 2026-10-17 by a Claude Sonnet source-review worker directly against the supplied
corpus text layer and rendered page images. No agent output was used as expected data. One
review pass only; the planned two independent Opus drafts and disagreement review were not
performed.

Source: `ressources/oap_91272_20210706.pdf` (corpus id `oap`).
SHA-256: `0c483af733f45a923ed8e212548fd23d835a0ce0307d98d54e28cf0fe9019cb1`.
Page numbers are 1-based PDF indices; the printed number is one lower (PDF p.33 = printed 32).

Reviewed pages: 2 (table of contents), 20-32 (chapter 7, Moulon), 33-36 (chapter 8,
Joliot Curie).

- p.33: chapter 8 orientations "viennent en complément" of chapter 7; general orientations;
  morphology: "objectif de R+4 moyen" for buildings with housing as main destination. This is
  worded as an objective, not a ceiling.
- p.34: implantation on the alignment along rue Joliot-Curie, without a uniform continuous
  front; ground floors open on the public space.
- p.35: two-level street hierarchy, rue Joliot-Curie "gabarit de l'ordre de 20 m" (a street
  gabarit, not a building limit); parking limited, underground or within the building volume.
- p.36: programming (housing for students, researchers and families); family and student
  housing mainly in the west of the district.
- p.25 (chapter 7): heights in UM zones are fixed by the règlement "à l'exception du quartier
  Joliot Curie, classé en zone UMG".
- The OAP contains no numeric height in metres, footprint ratio or parking count for the
  district; the must_not entries target that over-reading and the use of chapters 1 to 6.

Visual evidence: the diagram pages (rendered at 1.2x, PyMuPDF `page.get_pixmap`) are
[page34](page34.png), [page35](page35.png), [page36](page36.png) (diagrams: public spaces,
mobility, programming, each with the red dotted OAP perimeter) and [page33](page33.png). The
diagrams are raster images with no text layer, so the perimeter is not stated as a statement:
the site's presence in the OAP perimeter rests on the zoning oracle
(`evals/datasets/zoning/z01_joliot_curie.yaml`, legend item "Secteur à Orientation
d'Aménagement et de Programmation" present), and the fact "chapter 8 applies to the site"
combines that oracle with the p.33 text.

Brief vs documents: consistent with the brief (chapters 7 and 8 apply together; orientations
rather than hard figures; the only figures are "R+4 moyen" and "de l'ordre de 20 m").

No `must_flag`: the OAP leaves no ambiguity that the corpus fails to settle. It does not name
a young-workers residence; that classification belongs to the `destinations` task.

Render command:

```bash
uv run python -c "import pymupdf; d=pymupdf.open('ressources/oap_91272_20210706.pdf'); d[35].get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save('evals/fixtures/doc/d08_oap_joliot_curie/page36.png')"
```

Validation:

```text
uv run python -m evals.gt.check evals/datasets/doc/d08_oap_joliot_curie.yaml
OK d08_oap_joliot_curie [doc, verified] facts=10 must_flag=0 must_not=6

uv run python -m evals.gt.pages verify evals/datasets/doc/d08_oap_joliot_curie.yaml
13/13 quotes verified
```
