"""Build the corpus cache: ``uv run python -m agent.entrypoints.ingest [steps...] [overrides...]``.

Steps are ``corpus`` (extract, classify and split the PDFs) and ``georef`` (fit the raster
zoning plan to ground coordinates); both run when none is named. Other arguments are Hydra
overrides (``key=value``).
"""

import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from hydra.utils import instantiate
from omegaconf import DictConfig

from agent.adapters.georef.boundary import CommuneBoundaryClient
from agent.agents.config import PROJECT_ROOT, load_config, read_prompt
from agent.ingest.classify import make_classifier
from agent.ingest.georef.plan import georeference_plan, load_georef_settings
from agent.ingest.pipeline import ingest_corpus, load_settings
from agent.observability.logs import setup_logging

STEPS = ("corpus", "georef")


def _ingest_corpus(cfg: DictConfig) -> None:
    """Extract, classify and split the configured PDFs into ``corpus.dir``."""
    settings = load_settings(cfg.corpus)
    classifier = make_classifier(
        cfg.models, settings.classifier.model, read_prompt(settings.classifier.prompt)
    )
    ingest_corpus(settings, PROJECT_ROOT, classifier)


def _georeference(cfg: DictConfig) -> None:
    """Fit the raster zoning plan to ground coordinates and save the transform.

    Raises:
        ValueError: If the plan document is not among ``corpus.documents``.
    """
    settings = load_georef_settings(cfg.corpus.georef)
    paths = {str(document.id): str(document.path) for document in cfg.corpus.documents}
    if settings.document not in paths:
        msg = f"georef document {settings.document!r} is not in corpus.documents"
        raise ValueError(msg)
    boundary = instantiate(cfg.corpus.georef.boundary)
    if not isinstance(boundary, CommuneBoundaryClient):
        msg = "corpus.georef.boundary must build a CommuneBoundaryClient"
        raise TypeError(msg)
    plan = PROJECT_ROOT / Path(paths[settings.document])
    georeference_plan(settings, PROJECT_ROOT, plan, boundary, date.today())


def main() -> None:
    """Run the steps named in argv (all by default), with Hydra overrides from argv.

    Raises:
        ValueError: If an argument is neither a step nor a ``key=value`` override.
    """
    arguments = sys.argv[1:]
    steps = [argument for argument in arguments if "=" not in argument]
    unknown = [step for step in steps if step not in STEPS]
    if unknown:
        msg = f"unknown ingest step(s) {unknown}; expected some of {list(STEPS)}"
        raise ValueError(msg)
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    cfg = load_config([argument for argument in arguments if "=" in argument])
    setup_logging(cfg.policies.logging.level)
    if not steps or "corpus" in steps:
        _ingest_corpus(cfg)
    if not steps or "georef" in steps:
        _georeference(cfg)


if __name__ == "__main__":
    main()
