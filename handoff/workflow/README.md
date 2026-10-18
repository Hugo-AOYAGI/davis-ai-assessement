# Workflow site

This is the portable workflow explainer and recorded app demo, packaged from the final
authoring-site bundle. It illustrates current code and playbooks with saved examples;
it does not execute models or validate a live study.

From the repository root:

```sh
python -m http.server 4173 --bind 127.0.0.1 --directory handoff
```

Open http://localhost:4173/workflow/. Opening `index.html` through `file://` does not support
the JSON fetch used by the site. No build step, Node installation, credentials or backend is
needed. Keep the complete `assets/` directory, including font licenses and image provenance.

The app demo and screenshots predate submission cleanup. Negative studies can now omit the
envelope, and area caps trim physical polygons instead of scaling numbers alone. Those
changes are described in the updated workflow facts; the recording remains historical.

The remaining mechanisms are drawn per operation in `diagrams.js`: solid boxes are code,
dashed boxes are model reasoning, tables are data, arrows show execution, and plain lines
show a consistency relationship. One muted green focus identifies what matters in each
scene. Repair diagrams show a retained draft, a path edit and the same checks running again.
The diagrams explain implementation; they are not recordings of a tool-call trace.
