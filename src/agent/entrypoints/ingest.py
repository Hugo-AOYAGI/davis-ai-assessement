"""Build the corpus cache: ``uv run python -m agent.entrypoints.ingest [hydra overrides...]``."""

import sys

from dotenv import load_dotenv

from agent.agents.config import PROJECT_ROOT, load_config, read_prompt
from agent.ingest.classify import make_classifier
from agent.ingest.pipeline import ingest_corpus, load_settings
from agent.observability.logs import setup_logging


def main() -> None:
    """Ingest the configured PDFs into ``corpus.dir``, with Hydra overrides from argv."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    cfg = load_config(sys.argv[1:])
    setup_logging(cfg.policies.logging.level)
    settings = load_settings(cfg.corpus)
    classifier = make_classifier(
        cfg.models, settings.classifier.model, read_prompt(settings.classifier.prompt)
    )
    ingest_corpus(settings, PROJECT_ROOT, classifier)


if __name__ == "__main__":
    main()
