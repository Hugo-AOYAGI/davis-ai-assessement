from collections.abc import Mapping, Sequence

import shapely
from shapely.geometry.base import BaseGeometry

from agent.adapters.geo.cadastre import CadastralParcel, CadastreClient
from agent.adapters.geo.geocoder import AddressCandidate, AddressGeocoder
from agent.adapters.geo.records import (
    Located,
    ParcelCandidate,
    SiteDraft,
    SiteError,
    address_citation,
    adjacent_ids,
    mean_width,
    nearest_boundary,
    neighbour_records,
    parcel_citation,
)
from agent.contracts.findings.site import Parcel
from agent.runtime.geometry.boundaries import classify_boundaries
from agent.runtime.geometry.parcels import (
    DisjointParcelsError,
    polygon_from_rings,
    to_contract,
    to_shape,
    union_parcels,
)
from agent.runtime.geometry.projection import to_crs


class SiteSurveyor:
    """Turns an address and a parcel selection into a site, from the geocoder and the cadastre."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        geocoder: AddressGeocoder,
        cadastre: CadastreClient,
        crs: str,
        geographic_crs: str,
        decimals: int,
        grid_size_m: float,
        max_sliver_area_m2: float,
        neighbour_buffer_m: float,
        snap_tolerance_m: float,
        min_shared_ratio: float,
        collinear_angle_deg: float,
        geocoder_source: str,
        cadastre_source: str,
    ) -> None:
        """Create the surveyor.

        Args:
            geocoder: Address geocoder client.
            cadastre: Cadastre client.
            crs: Metric CRS of the site geometry, e.g. ``EPSG:2154``.
            geographic_crs: CRS of the services' coordinates, e.g. ``EPSG:4326``.
            decimals: Decimals kept on the site's coordinates.
            grid_size_m: Precision grid of the parcel union, in metres.
            max_sliver_area_m2: Holes and parts below this area are dropped from the union.
            neighbour_buffer_m: Distance around the site within which parcels are neighbours.
            snap_tolerance_m: Distance within which two limits count as shared.
            min_shared_ratio: Share of an edge that must lie on a neighbour to be separating.
            collinear_angle_deg: Largest direction change within one separating limit.
            geocoder_source: Source name cited for the geocoder record.
            cadastre_source: Source name cited for the cadastre records.
        """
        self._geocoder = geocoder
        self._cadastre = cadastre
        self._crs = crs
        self._geographic_crs = geographic_crs
        self._decimals = decimals
        self._grid_size_m = grid_size_m
        self._max_sliver_area_m2 = max_sliver_area_m2
        self._neighbour_buffer_m = neighbour_buffer_m
        self._snap_tolerance_m = snap_tolerance_m
        self._min_shared_ratio = min_shared_ratio
        self._collinear_angle_deg = collinear_angle_deg
        self._geocoder_source = geocoder_source
        self._cadastre_source = cadastre_source

    def candidates(
        self, longitude: float, latitude: float, radius_m: float
    ) -> tuple[ParcelCandidate, ...]:
        """Return the parcels within ``radius_m`` of a point, nearest first.

        Args:
            longitude: WGS84 longitude of the address point.
            latitude: WGS84 latitude of the address point.
            radius_m: Search radius, in metres.

        Returns:
            The candidates sorted by distance, then id.

        Raises:
            GeoServiceError: If the cadastre service fails.
        """
        point = self._point(longitude, latitude)
        area = to_crs(point.buffer(radius_m), self._crs, self._geographic_crs)
        located = {p.id: (p, self._shape(p)) for p in self._cadastre.intersecting(area)}
        candidates = [
            ParcelCandidate(
                id=parcel_id,
                contenance_m2=parcel.contenance_m2,
                distance_m=float(shape.distance(point)),
                contains_point=bool(shape.contains(point)),
                mean_width_m=mean_width(shape),
                touches=adjacent_ids(parcel_id, located, self._snap_tolerance_m),
            )
            for parcel_id, (parcel, shape) in located.items()
        ]
        return tuple(sorted(candidates, key=lambda c: (c.distance_m, c.id)))

    def draft(
        self, address: str, parcel_ids: Sequence[str], public_parcel_ids: Sequence[str]
    ) -> SiteDraft:
        """Compute the site formed by parcels, with boundaries typed against their neighbours.

        Args:
            address: Geocoder label of the address, exactly as the geocoder returns it.
            parcel_ids: Cadastral ids of the parcels forming the site.
            public_parcel_ids: Neighbouring parcels to treat as public space: they are left out
                of the neighbours used to type boundaries, so limits along them face the road.

        Returns:
            The site draft.

        Raises:
            SiteError: If the label, a parcel id or the selection is wrong (message for the model).
            GeoServiceError: If a service fails.
        """
        selected, public = dict.fromkeys(parcel_ids), dict.fromkeys(public_parcel_ids)
        if not selected:
            msg = "parcel_ids is empty: give at least one cadastral id from find_parcels"
            raise SiteError(msg)
        if overlap := [pid for pid in public if pid in selected]:
            msg = f"{overlap} are both in parcel_ids and public_parcel_ids; keep each in one list"
            raise SiteError(msg)
        candidate = self._geocode(address)
        parcels = [self._fetch(pid) for pid in selected]
        site = self._union([shape for _, shape in parcels], "the selected parcels")
        polygon = to_contract(site, self._crs, self._decimals)
        neighbours = self._neighbours(site, selected)
        if unknown := [pid for pid in public if pid not in neighbours]:
            msg = (
                f"public_parcel_ids {unknown} are not neighbours of the site; the neighbours are "
                f"{sorted(neighbours)}"
            )
            raise SiteError(msg)
        boundaries = classify_boundaries(
            polygon,
            [shape for pid, (_, shape) in neighbours.items() if pid not in public],
            self._snap_tolerance_m,
            self._min_shared_ratio,
            self._collinear_angle_deg,
        )
        point = self._point(candidate.longitude, candidate.latitude)
        nearest, distance = nearest_boundary(boundaries, point)
        shape = to_shape(polygon)
        return SiteDraft(
            address=candidate,
            parcels=tuple(self._parcel(parcel, shape) for parcel, shape in parcels),
            polygon=polygon,
            area_m2=float(shape.area),
            boundaries=boundaries,
            nearest_boundary=nearest,
            nearest_distance_m=distance,
            neighbours=neighbour_records(
                neighbours, shape.exterior, public, self._snap_tolerance_m
            ),
            citations=(
                address_citation(candidate, self._geocoder_source),
                *(parcel_citation(parcel, self._cadastre_source) for parcel, _ in parcels),
                *(parcel_citation(neighbours[pid][0], self._cadastre_source) for pid in public),
            ),
        )

    def _geocode(self, address: str) -> AddressCandidate:
        """Geocode the label again and check that the top match carries the same label."""
        matches = self._geocoder.search(address, limit=1)
        if not matches or _normalise(matches[0].label) != _normalise(address):
            found = repr(matches[0].label) if matches else "no match"
            msg = (
                f"address {address!r} is not a geocoder label (the geocoder returns {found} for "
                "it); pass the label exactly as geocode_address returned it"
            )
            raise SiteError(msg)
        return matches[0]

    def _fetch(self, parcel_id: str) -> Located:
        """Fetch a parcel by id and project it, turning unknown or malformed ids into errors."""
        try:
            parcel = self._cadastre.by_id(parcel_id)
        except ValueError as error:
            raise SiteError(str(error)) from error
        if parcel is None:
            msg = f"parcel {parcel_id} is not in the cadastre; use an id returned by find_parcels"
            raise SiteError(msg)
        return parcel, self._shape(parcel)

    def _union(self, shapes: Sequence[BaseGeometry], what: str) -> shapely.Polygon:
        """Merge parcel geometries into one polygon, reporting disjoint parts as a site error."""
        try:
            return union_parcels(shapes, self._grid_size_m, self._max_sliver_area_m2)
        except DisjointParcelsError as error:
            raise SiteError(str(error)) from error
        except ValueError as error:
            msg = f"{what} have no usable geometry ({error})"
            raise SiteError(msg) from error

    def _neighbours(
        self, site: shapely.Polygon, selected: Mapping[str, None]
    ) -> dict[str, Located]:
        """Return the parcels within the neighbour buffer of the site, selected ones excluded."""
        area = to_crs(site.buffer(self._neighbour_buffer_m), self._crs, self._geographic_crs)
        return {
            parcel.id: (parcel, self._shape(parcel))
            for parcel in self._cadastre.intersecting(area)
            if parcel.id not in selected
        }

    def _parcel(self, parcel: CadastralParcel, shape: BaseGeometry) -> Parcel:
        """Build the parcel contract: cadastral contenance, else the projected area."""
        polygon = self._union([shape], f"parcel {parcel.id}")
        area = parcel.contenance_m2 or float(polygon.area)
        return Parcel(
            id=parcel.id, area_m2=area, polygon=to_contract(polygon, self._crs, self._decimals)
        )

    def _point(self, longitude: float, latitude: float) -> shapely.Point:
        """Project a WGS84 point to the metric CRS."""
        return to_crs(shapely.Point(longitude, latitude), self._geographic_crs, self._crs)

    def _shape(self, parcel: CadastralParcel) -> BaseGeometry:
        """Return a parcel's geometry in the metric CRS."""
        return to_crs(polygon_from_rings(parcel.polygons), self._geographic_crs, self._crs)


def _normalise(label: str) -> str:
    """Case-fold a label and collapse its whitespace."""
    return " ".join(label.split()).casefold()
