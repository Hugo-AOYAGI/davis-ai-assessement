# Document ground-truth generation

## Lead

Build document benchmark items from `evals/README.md` and `evals/datasets/README.md` and the
case briefs in `evals/cases/doc.yaml`. `prompts/evals/tasks/doc.md` is the
task under test, not a ground-truth generation prompt. Never use doc_analyst
output as an oracle or change expected answers after observing an experiment.

Select a trap or a zone/program combination. Give each Sample worker the same
case brief, corpus document ids and page ranges, without another worker's draft.
The full-suite plan calls for two independent Opus drafts and review of their
disagreements; do not claim that process happened when only manual source review
was performed. For a manually reviewed smoke sample, record the actual method
and its limitation in an evidence note. Review every numeric assertion against
the source and inspect page images whenever formatting changes meaning.

Only mark an item verified once its expectations have been independently checked
against the corpus, every quote passes `evals.gt.pages verify`, and the item
passes `evals.gt.check`. Schema and quote matching alone do not prove that a rule
is in force or applies to the selected zone. Resolve discrepancies with examples
or fixtures from the actual source; fixture status is not verification evidence.

## Sample

Create one YAML item at `evals/datasets/doc/<id>.yaml` using the common schema.

1. Read the assigned case and relevant corpus pages using
   `uv run python -m evals.gt.pages find <doc> <terms>` and
   `uv run python -m evals.gt.pages read <doc> <pages>`.
   Confirm the sector, sub-sector, destination, exceptions and cross-references.
2. Fill only the orchestrator-style input: label, aim, documents, topics and
   context (zone, legend items, parcel ids if needed, program and program facts).
   Do not disclose expected regulatory values or the answer to the trap in input.
   Keep requested topics aligned with the statements actually evaluated.
3. Draft atomic statement facts with 1-based PDF page indices and short verbatim
   quotes. Identify central limits as critical. Record forbidden readings in
   `must_not`; add `must_flag` only for a real unresolved ambiguity or corpus gap.
4. Render and inspect original PDF pages for struck-through values, tables,
   graphics or other formatting lost in text extraction. Preserve the original
   text-layer quote even when it contains a superseded value, and record the
   visual interpretation separately; never fabricate a cleaned source quotation.
5. Save an evidence note under `evals/fixtures/doc/<id>/` with document path/hash,
   reviewed pages, actual review method, disagreements and visual evidence path.
   Be explicit if the planned two independent Opus drafts were not performed.
6. Run `uv run python -m evals.gt.check <item path>` and
   `uv run python -m evals.gt.pages verify <item path>`. Leave unresolved items
   as drafts. Report verified expectations, checks and limitations to the Lead.

Do not run experiments as part of Sample generation. Freeze reviewed ground truth
before passing its id to the experiment runner.
