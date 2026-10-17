import json
from collections.abc import Sequence

from pydantic import JsonValue

from agent.adapters.geo.geocoder import AddressCandidate
from agent.adapters.geo.records import EdgeTotal, ParcelCandidate, ParcelsDescription

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


def edge_rows(totals: Sequence[EdgeTotal]) -> dict[str, JsonValue]:
    """Render edge totals keyed by the kind of land across the edges."""
    return {
        total.other_side.value: {"count": total.count, "length_m": metres(total.length_m)}
        for total in totals
    }


def description_rows(description: ParcelsDescription) -> dict[str, JsonValue]:
    """Render a parcel selection's description for the model, without coordinates.

    Args:
        description: The described selection.

    Returns:
        The parcels and whether they form one piece; the union's facts when they do.
    """
    rows: dict[str, JsonValue] = {
        "parcels": [
            {
                "id": p.id,
                "contenance_m2": p.contenance_m2,
                "mean_width_m": metres(p.mean_width_m),
                "distance_m": metres(p.distance_m),
                "touches": list(p.touches),
            }
            for p in description.parcels
        ],
        "one_piece": description.one_piece,
    }
    if not description.one_piece:
        return {**rows, "part_areas_m2": [metres(a) for a in description.part_areas_m2]}
    return {
        **rows,
        "area_m2": metres(description.area_m2 or 0),
        "distance_m": metres(description.distance_m or 0),
        "edges": edge_rows(description.edges),
        "neighbours": [
            {
                "id": n.id,
                "contenance_m2": n.contenance_m2,
                "shared_length_m": metres(n.shared_length_m),
                "mean_width_m": metres(n.mean_width_m),
            }
            for n in description.neighbours
        ],
    }
