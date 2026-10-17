import pytest

from agent.contracts.evidence import ImageRegion
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from agent.tools.images.zone import zone_finalizer
from agent.tools.submit.factory import SubmissionRejected


def findings(page, box):
    return ZoneFindings(
        zone="UMG",
        overlays=(LegendItem(item="Périmètre d'OAP", applies=True, note="Hatched."),),
        rationale="Found by the road layout.",
        region=ImageRegion(doc="plan", page=page, region=box),
    )


def test_region_on_the_page_is_accepted_unchanged(images):
    submission = findings(1, (10, 10, 200, 100))
    assert zone_finalizer(images=images)(submission, {}) is submission


@pytest.mark.parametrize(
    ("page", "box", "message"),
    [
        (1, (0, 0, 401, 100), "region: the overview of plan p.1 is 400x200 px"),
        (2, (0, 0, 10, 10), "region: plan has 1 pages (1 to 1); page 2 does not exist"),
    ],
)
def test_region_off_the_page_is_rejected(images, page, box, message):
    with pytest.raises(SubmissionRejected) as rejected:
        zone_finalizer(images=images)(findings(page, box), {})
    (error,) = rejected.value.errors
    assert error.startswith(message)
