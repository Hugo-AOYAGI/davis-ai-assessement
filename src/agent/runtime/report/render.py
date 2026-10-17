from agent.contracts.study import VerifiedStudy
from agent.runtime.report.citations import CitationIndex, citations_section
from agent.runtime.report.envelope import envelope_section
from agent.runtime.report.markdown import one_line
from agent.runtime.report.sections import (
    admissibility_section,
    ambiguities_section,
    conditions_section,
    parking_section,
    regime_section,
    site_section,
)


def render_report(verified: VerifiedStudy, *, max_quote_chars: int) -> str:
    """Render a verified study as a Markdown report for an architect or developer.

    Claims reference the numbered table of citation checks at the end, e.g. ``[3]``; citations
    the gate did not check (geometric sources) are shown inline as ``(doc, p.X)`` or ``(doc)``.

    Args:
        verified: Study accepted by the ``submit_study`` gate.
        max_quote_chars: Length beyond which quotes are truncated in the citations table.

    Returns:
        The report, ending with a newline.
    """
    study = verified.study
    index = CitationIndex(verified.citation_checks)
    blocks = (
        f"# Buildability study: {one_line(study.address)}",
        f"**Program:** {study.program.strip()}",
        f"## Summary\n\n{study.summary.strip()}",
        site_section(verified.site, index),
        regime_section(study.regime, index),
        admissibility_section(study.admissibility, index),
        envelope_section(study.envelope, verified.envelope, index),
        parking_section(study.parking, index),
        conditions_section(study.conditions, index),
        ambiguities_section(study.ambiguities, index),
        citations_section(verified.citation_checks, max_quote_chars),
    )
    return "\n\n".join(blocks) + "\n"
