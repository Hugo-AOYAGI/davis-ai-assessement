# Coding standards

Rules apply to `src/`, `conf/`, `prompts/`, `evals/`, `scripts/`. Tests have a lighter regime
(see the last section). Exempt: the repository root, `ressources/`, `data/`, `outputs/`, `tools/`.

## Structure

1. **≤ 250 lines per file.** Split by responsibility before reaching the limit.
2. **≤ 5 files per folder**, `__init__.py` not counted. Sub-folders are not counted either.
   Benchmark datasets, source fixtures and case indexes are exempt from structural counts and
   lengths; their organization follows stable item IDs. Existing `adapters/images/pages.py`
   length and the root `contracts/` file count are accepted exceptions.
3. **File names never repeat their folder's name.**
   `adapters/geo/ban.py`, not `adapters/geo/geo_ban.py`; `contracts/study.py`, not `contracts/study_contract.py`.
4. **General names.** Packages and modules describe a role (`adapters`, `runtime`, `contracts`),
   not the reference case (no `gif`, `joliot`, `plu_*` in code paths).
5. **Respect the layering** (see `CLAUDE.md`): `contracts ← runtime ← adapters ← tools ← agents ← entrypoints`.
   A module never imports from a layer to its right. `runtime/` imports neither LangChain nor
   does any I/O.

## Configuration

6. **Zero configuration values in code.** Model names, temperatures, paths, thresholds,
   tolerances, limits, URLs and prompts live in Hydra configs (`conf/`) or prompt files
   (`prompts/`). Objects are built with `hydra.utils.instantiate` and `_target_`.
7. **Prompts are Markdown files** in `prompts/`, referenced from config. Tool descriptions,
   argument docstrings and short validation/recovery replies may live beside their schemas
   in Python; system instructions and multi-step playbooks may not.
8. **Secrets** come from `.env`, loaded once in `entrypoints/`. No `os.environ` reads elsewhere.

## LLM calls

9. **Single entry point**: models are created only in `src/agent/llm/`. No direct
   `ChatAnthropic(...)` (or any other client) anywhere else. Caching, cost tracking and tracing
   happen there.

## Typing

10. **Strict typing.** Every function parameter and return value is annotated. `ty check` passes
    with no warnings.
11. **No `Any` in public signatures.** Data crossing a module boundary is a Pydantic model
    (`contracts/`), frozen unless mutation is required.
    Local rendering/settings bundles may remain next to their implementation. Independent
    evaluation oracles own their typed schemas.

## Imports

12. **Top-level imports only.** No import inside a function, method or conditional block.
13. Absolute imports (`from agent.runtime.geometry import ...`).

## Documentation and comments

14. **Google-style docstring on every function, method and class.** Length matches the
    function: one line for the obvious, `Args:` / `Returns:` / `Raises:` sections when they add
    information. For tools, the docstring is what the LLM reads: write it for the model.
15. **No narrative comments.** No comment recounting history ("fixed bug where…", "previously
    we…"), no comment carrying context irrelevant to understanding the code in front of you.
    A comment is allowed only to explain a non-obvious *why* (e.g. the PLU article that justifies
    a rule).
16. No commented-out code.

## Logging and errors

17. **No `print`.** Use the logger from `observability/`.
    CLI result data may be written to stdout; diagnostics still use the logger.
18. No bare `except` or `except Exception` swallowing errors.

## Tooling

| Purpose | Tool | Command |
|---|---|---|
| Environment and dependencies | uv | `uv sync`, `uv add <pkg>`, `uv add --dev <pkg>` |
| Lint | ruff | `uv run ruff check .` |
| Format | ruff | `uv run ruff format .` |
| Types | ty | `uv run ty check` |
| Tests | pytest | `uv run pytest` |

All four checks must pass before a change is considered done. Ruff enforces rules 10, 12, 14,
16, 17, 18 (`ANN`, `PLC0415`, `D` google convention, `ERA`, `T20`, `BLE`) and function
complexity (`C90`, max 8).

## Tests

Tests live in `tests/`, mirroring `src/agent/`. They are exempt from the file/folder counts,
docstrings and annotations. They still follow formatting, top-level imports, no narrative
comments, and zero network access (external calls are replayed from fixtures).
Deterministic code (`runtime/`, `adapters/`, `contracts/`) is unit-tested; LLM behaviour is
measured by evals, not pytest.
