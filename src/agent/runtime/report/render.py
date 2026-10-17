from agent.contracts.study import VerifiedStudy
from agent.runtime.report.citations import CitationIndex, citations_section, evidence_section
from agent.runtime.report.markdown import one_line
from agent.runtime.report.program import admissibility_section, envelope_section, parking_section
from agent.runtime.report.sections import (
    ambiguities_section,
    conditions_section,
    regime_section,
    site_section,
)


def render_report(verified: VerifiedStudy, *, max_quote_chars: int, crops_link_base: str) -> str:
    """Render a verified study as a Markdown report for an architect or developer.

    Claims reference the numbered table of citation checks at the end, e.g. ``[3]``; citations
    the gate did not check (geometric sources) are shown inline as ``(doc, p.X)`` or ``(doc)``.
    Evidence crops are linked by file name under ``crops_link_base``: the caller puts the files
    there.

    Args:
        verified: Study accepted by the ``submit_study`` gate.
        max_quote_chars: Length beyond which quotes are truncated in the citations table.
        crops_link_base: Directory, relative to the report, the evidence crops are linked from.

    Returns:
        The report, ending with a newline.
    """
    study = verified.study
    index = CitationIndex(verified.citation_checks)
    blocks = (
        f"# Buildability study: {one_line(study.address)}",
        f"**Program:** {study.program.strip()}",
        f"## Summary\n\n{study.summary.strip()}",
        site_section(verified.site, verified.boundaries, index),
        regime_section(study.regime, verified.zone, index),
        admissibility_section(study.admissibility, index),
        envelope_section(verified.envelope, index),
        parking_section(study.parking, index),
        conditions_section(study.conditions, index),
        ambiguities_section(study.ambiguities, index),
        evidence_section(verified.evidence, crops_link_base),
        citations_section(verified.citation_checks, max_quote_chars),
    )
    return "\n\n".join(blocks) + "\n"
