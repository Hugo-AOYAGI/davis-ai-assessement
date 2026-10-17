import pytest
from omegaconf import OmegaConf

from agent.agents.config import load_config, read_prompt
from evals.harness.items import DocContext, DocInput, SurveyorInput, ZoningInput
from evals.harness.runs.texts import TaskWords, task_text


@pytest.fixture(scope="module")
def cfg():
    return load_config(["+eval=harness"])


@pytest.fixture(scope="module")
def words(cfg):
    return TaskWords.model_validate(OmegaConf.to_container(cfg.eval.eval_tasks.texts))


def flat(text: str) -> str:
    return " ".join(text.split())


def render(cfg, words, level, task):
    template = read_prompt(cfg.eval.eval_tasks.templates[level])
    return task_text(task, template, words=words, language=cfg.agent.language)


def playbook(cfg) -> str:
    return flat(read_prompt(cfg.agent.playbooks.study.path))


def test_surveyor_task_gives_address_program_and_language(cfg, words):
    text = render(cfg, words, "surveyor", SurveyorInput(address="4 rue Joliot Curie"))
    assert "Address: 4 rue Joliot Curie" in text
    assert f"Program: {words.no_program}" in text
    assert f"free text in {cfg.agent.language}" in text
    assert "`site`" in text
    with_program = render(cfg, words, "surveyor", SurveyorInput(address="a", program="housing"))
    assert "Program: housing" in with_program


def test_zoning_task_gives_the_parcel_ids(cfg, words):
    task = ZoningInput(address="4 rue Joliot Curie", parcel_ids=("A1", "A2"), program="offices")
    text = render(cfg, words, "zoning", task)
    assert "Parcel ids of the site: A1, A2" in text
    assert "Program: offices" in text
    assert "`zone`" in text
    assert "applying or not" in text
    assert "applies" in playbook(cfg)


def test_doc_task_mirrors_the_playbook_fields_and_wording(cfg, words):
    task = DocInput(
        label="rules",
        aim="the height limits",
        documents=("plu_reglement",),
        topics=("height", "parking"),
        context=DocContext(
            zone="UGa",
            legend_items=("Périmètre, d'OAP", "EBC"),
            parcel_ids=("91272000AB0001",),
            program="housing",
            facts=("40 dwellings",),
        ),
    )
    text = flat(render(cfg, words, "doc", task))
    for line in (
        "- label: `rules`",
        "- aim: the height limits",
        "- documents: plu_reglement",
        "- topics: `height`, `parking`",
        "- zone: UGa",
        "- legend items that apply: Périmètre, d'OAP; EBC",
        "- parcel ids: 91272000AB0001",
        "- program: housing",
        "- known program facts: 40 dwellings",
        "artifact `notes.rules`",
    ):
        assert line in text
    shared = (
        "Give the topics exactly as listed: `submit_notes` requires one note per topic and no "
        "note outside the list.",
        "(quotes stay verbatim in the language of the documents)",
    )
    for sentence in shared:
        assert sentence in text
        assert sentence in playbook(cfg)
    for field in ("- label:", "- aim:", "- documents:", "- topics:"):
        assert field in playbook(cfg)


def test_doc_task_with_empty_fields(cfg, words):
    task = DocInput(label="oap", aim="x", context=DocContext(zone="UA", program="housing"))
    text = render(cfg, words, "doc", task)
    assert f"- documents: {words.all_documents}" in text
    assert f"- topics: {words.none}" in text
    assert f"- legend items that apply: {words.none}" in text
    assert "$" not in text
