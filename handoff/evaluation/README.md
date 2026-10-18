# Historical benchmark evidence

Open [the report](../evaluation.html) for the comparison. These are saved runs from
**18 October 2026**, before the submission cleanup. No new paid benchmark was run after
the fixes. In particular, geometry clipping, consistency validation and failure capture have
since changed; historical failures and pass counts remain historical observations.

| Configuration | Score snapshot | Original record run |
|---|---|---|
| v1 Haiku, component tasks | `v1-components/scores.json` | `2026-10-18/00-03-33` |
| v1 Haiku, full studies | `v1-e2e/scores.json` | `2026-10-18/02-03-56` |
| v2 Haiku | `v2-haiku/scores.json` | `2026-10-18/12-25-42` |
| v2 Sonnet | `v2-sonnet/scores.json` | `2026-10-18/13-15-14` |

Each folder includes the original execution configuration and overrides. v1 component scores
were rescored in `02-03-59`; their execution configuration comes from `00-03-33`, not the
rescore configuration. [manifest.json](manifest.json) records original/exported score hashes
and source identities. Workstation-specific top-level run paths were made relative in the
exported scores; numeric results and judge decisions were preserved.

The exact code revisions were not captured with the original runs. Saved configurations
document model/settings differences but cannot reconstruct every source change. v2 added
georeferenced parcel views alongside rendering and context-pruning changes; this comparison
does not isolate a single cause. There is one run per configuration, without a repeated-run
significance analysis.

The 70 cases contain 451 scored facts (including the synthetic refusal score), of which 193
are critical. Expected answers were source-reviewed by model workers, not signed off by a
human. Review depth differs by level; see [dataset provenance](../../evals/datasets/README.md).
The Sonnet judge is uncalibrated. Item pass requires critical grounded facts and no forbidden
claims; additional flags, citations and envelope diagnostics have narrower independent roles.
See [scoring definitions](../../evals/README.md#4-scoring-definitions).

Raw traces/records remain in the local ignored outputs and are not shipped in this compact
bundle. The retained scores are sufficient to reproduce the tables/charts, not to rerun
model judging. Never delete original `00-03-33` records while relying on its rescore.

To regenerate the self-contained HTML from the snapshots, from the repository root:

```sh
uv run python -m scripts.build_eval_report handoff
```

`template.html` owns explanatory prose/presentation; the generator computes chart/table data,
case pass grids, topic groupings, forbidden claims and costs from the score snapshots. It
rejects comparisons with different item/fact denominators. Do not hand-edit the generated
report's data.
