from collections.abc import Iterable, Mapping, Sequence, Set

import shapely
from shapely.geometry.base import BaseGeometry

from agent.adapters.geo.cadastre import CadastralParcel, CadastreClient
from agent.adapters.geo.geocoder import AddressCandidate, AddressGeocoder
from agent.adapters.geo.records import (
    Located,
    ParcelCandidate,
    ParcelsDescription,
    SiteError,
    SurveySettings,
    address_citation,
    edge_totals,
    neighbour_facts,
    parcel_citation,
    parcel_facts,
    unique_ids,
)
from agent.contracts.findings.site import Edge, Parcel, ParcelChoice, Site
from agent.runtime.geometry.edges import site_edges
from agent.runtime.geometry.parcels import (
    DisjointParcelsError,
    polygon_from_rings,
    to_contract,
    union_parcels,
)
from agent.runtime.geometry.projection import to_crs


class SiteSurveyor:
    """Describes parcels and builds the site from a parcel choice (geocoder and cadastre)."""

    def __init__(
        self, *, geocoder: AddressGeocoder, cadastre: CadastreClient, settings: SurveySettings
    ) -> None:
        """Create the surveyor.

        Args:
            geocoder: Address geocoder client.
            cadastre: Cadastre client.
            settings: CRSs, union and edge tolerances, cited source names.
        """
        self._geocoder = geocoder
        self._cadastre = cadastre
        self._settings = settings

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
            ServiceError: If the cadastre service fails.
        """
        point = self._point(longitude, latitude)
        located = {p.id: (p, self._shape(p)) for p in self._intersecting(point.buffer(radius_m))}
        candidates = [
            ParcelCandidate(
                **facts.model_dump(), contains_point=bool(located[facts.id][1].contains(point))
            )
            for facts in parcel_facts(located, point, self._settings.snap_tolerance_m)
        ]
        return tuple(sorted(candidates, key=lambda c: (c.distance_m, c.id)))

    def describe(
        self, longitude: float, latitude: float, parcel_ids: Sequence[str]
    ) -> ParcelsDescription:
        """Describe a parcel selection: each parcel, and the site their union would form.

        Args:
            longitude: WGS84 longitude of the address point.
            latitude: WGS84 latitude of the address point.
            parcel_ids: Cadastral ids of the selection.

        Returns:
            The description; the union's facts are left empty when the parcels are not one piece.

        Raises:
            SiteError: If an id is wrong or the selection is empty (message for the model).
            ServiceError: If the cadastre service fails.
        """
        point = self._point(longitude, latitude)
        located = {pid: self._fetch(pid) for pid in unique_ids(parcel_ids)}
        parcels = parcel_facts(located, point, self._settings.snap_tolerance_m)
        try:
            site = self._union(shape for _, shape in located.values())
        except DisjointParcelsError as error:
            return ParcelsDescription(
                parcels=parcels, one_piece=False, part_areas_m2=error.part_areas_m2
            )
        neighbours = self._neighbours(site, located)
        return ParcelsDescription(
            parcels=parcels,
            one_piece=True,
            area_m2=float(site.area),
            distance_m=float(site.distance(point)),
            edges=edge_totals(self._edges(site, neighbours, frozenset())),
            neighbours=neighbour_facts(neighbours, site, self._settings.snap_tolerance_m),
        )

    def site(self, choice: ParcelChoice) -> Site:
        """Build the site from a parcel choice, checking the address label against the geocoder.

        Args:
            choice: The agent's choice, including the neighbours it declared public land.

        Returns:
            The site: parcels, union polygon, area, edges and geometric citations.

        Raises:
            SiteError: If the label, an id or the selection is wrong (message for the model).
            ServiceError: If a service fails.
        """
        candidate = self._geocode(choice.address)
        located = {pid: self._fetch(pid) for pid in unique_ids(choice.parcel_ids)}
        try:
            site = self._union(shape for _, shape in located.values())
        except DisjointParcelsError as error:
            raise SiteError(str(error)) from error
        neighbours = self._neighbours(site, located)
        settings = self._settings
        return Site(
            address=candidate.label,
            longitude=candidate.longitude,
            latitude=candidate.latitude,
            choice=choice,
            parcels=tuple(self._parcel(parcel, shape) for parcel, shape in located.values()),
            polygon=to_contract(site, settings.crs, settings.decimals),
            area_m2=float(site.area),
            edges=self._edges(site, neighbours, {p.id for p in choice.public_parcels}),
            citations=(
                address_citation(candidate, settings.geocoder_source),
                *(parcel_citation(p, settings.cadastre_source) for p, _ in located.values()),
            ),
        )

    def parcels(self, parcel_ids: Sequence[str]) -> tuple[Parcel, ...]:
        """Return parcels with their polygons in the metric CRS.

        Args:
            parcel_ids: Cadastral ids.

        Returns:
            The parcels, in the given order without duplicates.

        Raises:
            SiteError: If an id is wrong or none is given (message for the model).
            ServiceError: If the cadastre service fails.
        """
        located = [self._fetch(pid) for pid in unique_ids(parcel_ids)]
        return tuple(self._parcel(parcel, shape) for parcel, shape in located)

    def _geocode(self, address: str) -> AddressCandidate:
        """Geocode the label again and check that the top match carries the same label."""
        matches = self._geocoder.search(address, limit=1)
        if not matches or _normalise(matches[0].label) != _normalise(address):
            found = repr(matches[0].label) if matches else "no match"
            msg = (
                f"address {address!r} is not a geocoder label (the geocoder returns {found} for "
                "it); pass the label exactly as geocode returned it"
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

    def _union(self, shapes: Iterable[BaseGeometry]) -> shapely.Polygon:
        """Merge parcel geometries into one polygon.

        Raises:
            DisjointParcelsError: If the parcels form several parts.
            SiteError: If nothing with an area remains.
        """
        settings = self._settings
        try:
            return union_parcels(list(shapes), settings.grid_size_m, settings.max_sliver_area_m2)
        except DisjointParcelsError:
            raise
        except ValueError as error:
            msg = f"the selected parcels have no usable geometry ({error})"
            raise SiteError(msg) from error

    def _intersecting(self, area: BaseGeometry) -> tuple[CadastralParcel, ...]:
        """Return the parcels intersecting a metric area."""
        settings = self._settings
        return self._cadastre.intersecting(to_crs(area, settings.crs, settings.geographic_crs))

    def _neighbours(
        self, site: shapely.Polygon, selected: Mapping[str, Located]
    ) -> dict[str, Located]:
        """Return the parcels within the neighbour buffer of the site, selected ones excluded."""
        return {
            parcel.id: (parcel, self._shape(parcel))
            for parcel in self._intersecting(site.buffer(self._settings.neighbour_buffer_m))
            if parcel.id not in selected
        }

    def _edges(
        self, site: shapely.Polygon, neighbours: Mapping[str, Located], public: Set[str]
    ) -> tuple[Edge, ...]:
        """Describe each exterior edge of the site by what lies across it, given public ids."""
        settings = self._settings
        return site_edges(
            to_contract(site, settings.crs, settings.decimals),
            {pid: shape for pid, (_, shape) in neighbours.items()},
            snap_tolerance_m=settings.snap_tolerance_m,
            min_shared_ratio=settings.min_shared_ratio,
            public=public,
        )

    def _parcel(self, parcel: CadastralParcel, shape: BaseGeometry) -> Parcel:
        """Build the parcel contract: cadastral contenance, else the projected area."""
        polygon = self._union([shape])
        area = parcel.contenance_m2 or float(polygon.area)
        contract = to_contract(polygon, self._settings.crs, self._settings.decimals)
        return Parcel(id=parcel.id, area_m2=area, polygon=contract)

    def _point(self, longitude: float, latitude: float) -> shapely.Point:
        """Project a WGS84 point to the metric CRS."""
        point = shapely.Point(longitude, latitude)
        return to_crs(point, self._settings.geographic_crs, self._settings.crs)

    def _shape(self, parcel: CadastralParcel) -> BaseGeometry:
        """Return a parcel's geometry in the metric CRS."""
        shape = polygon_from_rings(parcel.polygons)
        return to_crs(shape, self._settings.geographic_crs, self._settings.crs)


def _normalise(label: str) -> str:
    """Case-fold a label and collapse its whitespace."""
    return " ".join(label.split()).casefold()
