# End-to-end dataset generation

## Lead

Read `evals/README.md`, the current `VerifiedStudy` and envelope contracts, and the
component generation prompts. Select a planned site and program. Delegate independent
source checks for cadastral selection, archived 2021 zoning and regulatory documents.
Preserve the source files, their versions, checked pages and actual review method.
Never obtain expected answers from the agent run being evaluated.

## Sample

Write one YAML item under `evals/datasets/e2e/`. Use component facts for the same site
where available and identify these with `from_items`. Read additional regulatory facts
directly from the corpus; cite 1-based PDF pages. Check every key against the current
contracts rather than copying old examples. Record alternatives only when the sources
leave the interpretation open. Supply program facts, never the expected regulatory answer,
in the input. Verify all quotes with `evals.gt.pages` and validate with `evals.gt.check`.

Calculate layout-independent figures from the independently checked cadastral geometry
and expected rules. A freely chosen two-building layout does not have one expected
proposal volume: do not turn one arbitrary layout into the oracle. Score the site area,
minimum green area and cited envelope parameters; the harness also recomputes the
proposal from the submitted layout. Explicitly document any omitted volume oracle.

Keep unresolved source disagreements as drafts. Describe the checks actually performed;
do not claim independent Opus drafts or human sign-off unless they occurred. A verified
smoke sample establishes source-checked facts, not completion of the full benchmark plan.
