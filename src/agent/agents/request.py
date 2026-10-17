from string import Template

from agent.contracts.inputs.case import Case


def case_request(case: Case, template: str, *, no_facts: str) -> str:
    """Render the initial human message of a run from its case.

    Args:
        case: The run's input.
        template: Request template (``agent.request`` prompt file) using ``$address``,
            ``$program`` and ``$facts``.
        no_facts: Text standing for ``$facts`` when the case gives none (``agent.no_facts``).

    Returns:
        The message text, with one ``- <fact>`` line per fact.

    Raises:
        KeyError: If the template uses a placeholder other than these three.
    """
    facts = "\n".join(f"- {fact}" for fact in case.facts) if case.facts else no_facts
    return Template(template).substitute(address=case.address, program=case.program, facts=facts)
