import json
import math
from collections.abc import Sequence

from pydantic import JsonValue

from agent.adapters.geo.geocoder import AddressCandidate
from agent.adapters.geo.records import ParcelCandidate, SiteDraft
from agent.contracts.geometry import BoundaryKind

_METRE_DECIMALS = 1
_SCORE_DECIMALS = 2


def to_json(value: JsonValue) -> str:
    """Serialise a tool result compactly, keeping accented characters readable."""
    return json.dumps(value, ensure_ascii=False)


def metres(value: float) -> float:
    """Round a length or an area for the model: a decimetre is precise enough."""
    return round(value, _METRE_DECIMALS)


def address_rows(candidates: Sequence[AddressCandidate]) -> list[JsonValue]:
    """Render geocoder candidates for the model.

    Args:
        candidates: Geocoder matches, best first.

    Returns:
        One JSON object per candidate.
    """
    return [
        {
            "label": c.label,
            "score": round(c.score, _SCORE_DECIMALS),
            "kind": c.kind,
            "longitude": c.longitude,
            "latitude": c.latitude,
            "city": c.city,
            "postcode": c.postcode,
            "citycode": c.citycode,
        }
        for c in candidates
    ]


def parcel_rows(candidates: Sequence[ParcelCandidate]) -> list[JsonValue]:
    """Render parcel candidates for the model.

    Args:
        candidates: Parcels near an address point, nearest first.

    Returns:
        One JSON object per parcel.
    """
    return [
        {
            "id": c.id,
            "contenance_m2": c.contenance_m2,
            "distance_m": metres(c.distance_m),
            "contains_point": c.contains_point,
            "mean_width_m": metres(c.mean_width_m),
            "touches": list(c.touches),
        }
        for c in candidates
    ]


def site_summary(draft: SiteDraft) -> dict[str, JsonValue]:
    """Summarise a site draft for the model, without its coordinates.

    Args:
        draft: The computed site.

    Returns:
        Area, parcels, boundary length and edge count per type, the boundary nearest to the
        address point, and the neighbours.
    """
    boundaries: dict[str, JsonValue] = {}
    for kind in BoundaryKind:
        edges = [b for b in draft.boundaries if b.kind is kind]
        length = sum(math.dist(b.start, b.end) for b in edges)
        boundaries[kind.value] = {"length_m": metres(length), "edges": len(edges)}
    return {
        "area_m2": metres(draft.area_m2),
        "parcels": [{"id": p.id, "contenance_m2": p.area_m2} for p in draft.parcels],
        "boundaries": boundaries,
        "nearest_boundary": {
            "kind": draft.nearest_boundary.kind.value,
            "distance_m": metres(draft.nearest_distance_m),
        },
        "neighbours": [
            {
                "id": n.id,
                "contenance_m2": n.contenance_m2,
                "shared_length_m": metres(n.shared_length_m),
                "mean_width_m": metres(n.mean_width_m),
                "public": n.public,
            }
            for n in draft.neighbours
        ],
    }
