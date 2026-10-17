"use client";

import { useId, useMemo } from "react";
import type {
  BoundaryKind,
  EnvelopeStudy,
  Point,
  Polygon,
  VerifiedStudy,
} from "@/lib/study-types";
import {
  BOUNDARY_COLORS,
  BOUNDARY_KINDS,
  BOUNDARY_LABELS,
  FOOTPRINT_COLOR,
} from "./colors";
import { buildingColors, findBound, massingTag } from "./envelope";
import { formatArea, formatLength } from "./format";
import {
  bounds,
  centroid,
  distance,
  niceLength,
  outwardNormal,
  polygonToLocal,
  ringToLocal,
} from "./geometry";

/** SVG y grows downwards: flip north. */
const svg = ([x, y]: Point) => `${x.toFixed(2)},${(-y).toFixed(2)}`;

function ringPath(ring: Point[]): string {
  return `M${ring.map(svg).join("L")}Z`;
}

function polygonPath(polygon: Polygon): string {
  return [polygon.exterior, ...polygon.holes].map(ringPath).join("");
}

const samePoint = (a: Point, b: Point) =>
  Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6;

/** The site edge a labelled boundary lies on, for what is across it. */
function edgeOf(study: VerifiedStudy, start: Point, end: Point) {
  return study.site.edges.find(
    (e) =>
      (samePoint(e.start, start) && samePoint(e.end, end)) ||
      (samePoint(e.start, end) && samePoint(e.end, start)),
  );
}

function usePlan(study: VerifiedStudy, envelope: EnvelopeStudy | null) {
  return useMemo(() => {
    const origin = centroid(study.site.polygon.exterior);
    const site = polygonToLocal(study.site.polygon, origin);
    const outline = envelope
      ? (envelope.proposal.footprint ??
        findBound(envelope, "windows")?.footprint ??
        null)
      : null;
    const footprint = outline ? polygonToLocal(outline, origin) : null;
    const known = envelope
      ? [
          ...envelope.rules.buildings.map((b) => b.building),
          ...study.study.admissibility.map((a) => a.building),
        ]
      : [];
    const colors = envelope
      ? buildingColors(envelope)
      : new Map<string, string>();
    const buildings = (envelope?.proposal.buildings ?? []).flatMap((b) => {
      if (!b.footprint) return [];
      const polygon = polygonToLocal(b.footprint, origin);
      return [
        {
          name: b.building,
          tag: massingTag(b, known),
          height: b.max_height_m,
          area: b.footprint_area_m2,
          polygon,
          center: centroid(polygon.exterior),
          color: colors.get(b.building) ?? FOOTPRINT_COLOR,
        },
      ];
    });
    const edges = study.boundaries.map((b) => {
      const start = ringToLocal([b.start], origin)[0];
      const end = ringToLocal([b.end], origin)[0];
      const edge = edgeOf(study, b.start, b.end);
      return {
        kind: b.kind,
        start,
        end,
        length: distance(start, end),
        normal: outwardNormal(start, end, site.exterior),
        publicLand: edge?.other_side === "public_land",
        neighbours: edge?.neighbours ?? [],
      };
    });
    const box = bounds(site.exterior);
    const width = box.maxX - box.minX;
    const height = box.maxY - box.minY;
    const extent = Math.max(width, height);
    return { site, footprint, buildings, edges, box, width, height, extent };
  }, [study, envelope]);
}

function NorthArrow({ x, y, size }: { x: number; y: number; size: number }) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      aria-hidden
    >
      <path
        d={`M0,${-size} L${size * 0.45},${size * 0.5} L0,${size * 0.2} L${-size * 0.45},${size * 0.5}Z`}
        className="fill-foreground"
      />
      <text
        y={-size * 1.25}
        textAnchor="middle"
        fontSize={size * 0.8}
        className="fill-foreground font-semibold"
      >
        N
      </text>
    </g>
  );
}

function ScaleBar({
  x,
  y,
  length,
  fontSize,
}: {
  x: number;
  y: number;
  length: number;
  fontSize: number;
}) {
  const tick = fontSize * 0.4;
  return (
    <g
      aria-hidden
      className="stroke-foreground"
    >
      <path
        d={`M${x},${y - tick}V${y}H${x + length}V${y - tick}`}
        fill="none"
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
      <text
        x={x + length / 2}
        y={y + fontSize * 1.1}
        textAnchor="middle"
        fontSize={fontSize}
        className="fill-foreground stroke-none"
      >
        {length} m
      </text>
    </g>
  );
}

/** Parcel id without its commune prefix: `91272000CR0249` → `CR0249`. */
const parcelLabel = (id: string) => id.replace(/^\d{5,}(?=[A-Z])/, "");

function edgeTitle(e: {
  kind: BoundaryKind;
  length: number;
  publicLand: boolean;
  neighbours: string[];
}) {
  const base = `${BOUNDARY_LABELS[e.kind]} limit · ${formatLength(e.length)}`;
  if (!e.publicLand) return base;
  return e.neighbours.length > 0
    ? `${base} · public land (${e.neighbours.map(parcelLabel).join(", ")}, declared by the surveyor)`
    : `${base} · public land`;
}

export function SitePlan({
  study,
  envelope,
}: {
  study: VerifiedStudy;
  envelope: EnvelopeStudy | null;
}) {
  const { site, footprint, buildings, edges, box, width, height, extent } =
    usePlan(study, envelope);
  const declared = study.site.choice.public_parcels ?? [];
  const titleId = useId();
  const pad = extent * 0.14;
  const fontSize = extent * 0.032;
  const labelMin = Math.max(extent * 0.12, 4);
  const viewBox = [
    box.minX - pad,
    -box.maxY - pad,
    width + 2 * pad,
    height + 2 * pad,
  ].join(" ");
  const scale = niceLength(width * 0.3);
  const totals = BOUNDARY_KINDS.map((kind) => {
    const ofKind = edges.filter((e) => e.kind === kind);
    return {
      kind,
      count: ofKind.length,
      length: ofKind.reduce((s, e) => s + e.length, 0),
    };
  });

  return (
    <figure>
      <svg
        viewBox={viewBox}
        role="img"
        aria-labelledby={titleId}
        className="bg-muted/30 h-auto max-h-[22rem] w-full rounded-lg border"
      >
        <title id={titleId}>
          {[
            `Site plan: site of ${formatArea(study.site.area_m2)}`,
            footprint && "footprint after setbacks with windows dashed",
            buildings.length > 0 &&
              `proposed buildings ${buildings.map((b) => `${b.tag} (${formatArea(b.area)}, ${formatLength(b.height, 0)})`).join(", ")}`,
            "north up.",
          ]
            .filter(Boolean)
            .join(", ")}
        </title>
        <path
          d={polygonPath(site)}
          fillRule="evenodd"
          className="fill-muted stroke-foreground/40"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
        {footprint && (
          <path
            d={polygonPath(footprint)}
            fillRule="evenodd"
            fill={FOOTPRINT_COLOR}
            fillOpacity={0.2}
            stroke={FOOTPRINT_COLOR}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {buildings.map((b) => (
          <path
            key={b.name}
            d={polygonPath(b.polygon)}
            fillRule="evenodd"
            fill={b.color}
            fillOpacity={0.45}
            stroke={b.color}
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
          >
            <title>{`${b.name} · ${formatArea(b.area)} · ${formatLength(b.height, 0)}`}</title>
          </path>
        ))}
        {edges.map((e, i) => (
          <line
            key={i}
            x1={e.start[0]}
            y1={-e.start[1]}
            x2={e.end[0]}
            y2={-e.end[1]}
            stroke={BOUNDARY_COLORS[e.kind]}
            strokeWidth={3}
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          >
            <title>{edgeTitle(e)}</title>
          </line>
        ))}
        {edges
          .filter((e) => e.length >= labelMin)
          .map((e, i) => {
            const mx = (e.start[0] + e.end[0]) / 2 + e.normal[0] * fontSize;
            const my = (e.start[1] + e.end[1]) / 2 + e.normal[1] * fontSize;
            return (
              <text
                key={i}
                x={mx}
                y={-my}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={fontSize}
                strokeWidth={fontSize * 0.3}
                paintOrder="stroke"
                className="fill-foreground stroke-card tabular-nums"
                aria-hidden
              >
                {formatLength(e.length)}
              </text>
            );
          })}
        {buildings.map((b) => (
          <text
            key={b.name}
            x={b.center[0]}
            y={-b.center[1]}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={fontSize}
            strokeWidth={fontSize * 0.3}
            paintOrder="stroke"
            className="fill-foreground stroke-card font-medium tabular-nums"
            aria-hidden
          >
            {`${b.tag} · ${formatLength(b.height, 0)}`}
          </text>
        ))}
        <NorthArrow
          x={box.maxX + pad * 0.5}
          y={-box.maxY - pad * 0.25}
          size={fontSize * 1.2}
        />
        <ScaleBar
          x={box.minX - pad * 0.6}
          y={-box.minY + pad * 0.45}
          length={scale}
          fontSize={fontSize}
        />
      </svg>
      <figcaption className="text-muted-foreground mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {totals.map(({ kind, count, length }) => (
          <span
            key={kind}
            className="inline-flex items-center gap-1.5"
          >
            <span
              aria-hidden
              className="h-0.5 w-4 rounded-full"
              style={{ backgroundColor: BOUNDARY_COLORS[kind] }}
            />
            {BOUNDARY_LABELS[kind]}{" "}
            {count > 0 ? `· ${count} · ${formatLength(length)}` : "· none"}
          </span>
        ))}
        {footprint && (
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-3 rounded-sm border border-dashed"
              style={{
                borderColor: FOOTPRINT_COLOR,
                backgroundColor: `color-mix(in oklch, ${FOOTPRINT_COLOR} 20%, transparent)`,
              }}
            />
            After setbacks with windows
          </span>
        )}
        {buildings.map((b) => (
          <span
            key={b.name}
            className="inline-flex items-center gap-1.5"
            title={b.name}
          >
            <span
              aria-hidden
              className="size-3 rounded-sm"
              style={{ backgroundColor: b.color }}
            />
            {b.tag}
          </span>
        ))}
      </figcaption>
      {declared.length > 0 && (
        <ul className="text-muted-foreground mt-2 space-y-0.5 text-xs leading-relaxed">
          {declared.map((p) => (
            <li key={p.id}>
              <span className="text-foreground font-medium">
                {parcelLabel(p.id)}
              </span>{" "}
              declared public land by the surveyor: {p.reason}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
