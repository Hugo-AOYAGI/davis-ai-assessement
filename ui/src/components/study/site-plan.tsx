"use client";

import { useId, useMemo } from "react";
import type { Point, Polygon, VerifiedStudy } from "@/lib/study-types";
import {
  BOUNDARY_COLORS,
  BOUNDARY_KINDS,
  BOUNDARY_LABELS,
  FOOTPRINT_COLOR,
} from "./colors";
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

function usePlan(study: VerifiedStudy) {
  return useMemo(() => {
    const origin = centroid(study.site.polygon.exterior);
    const site = polygonToLocal(study.site.polygon, origin);
    const footprint = study.envelope.footprint
      ? polygonToLocal(study.envelope.footprint, origin)
      : null;
    const edges = study.boundaries.map((b) => {
      const start = ringToLocal([b.start], origin)[0];
      const end = ringToLocal([b.end], origin)[0];
      return {
        kind: b.kind,
        start,
        end,
        length: distance(start, end),
        normal: outwardNormal(start, end, site.exterior),
      };
    });
    const box = bounds(site.exterior);
    const width = box.maxX - box.minX;
    const height = box.maxY - box.minY;
    const extent = Math.max(width, height);
    return { site, footprint, edges, box, width, height, extent };
  }, [study]);
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

export function SitePlan({ study }: { study: VerifiedStudy }) {
  const { site, footprint, edges, box, width, height, extent } = usePlan(study);
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
          {`Site plan: site of ${formatArea(study.envelope.site_area_m2)}, buildable footprint of ${formatArea(study.envelope.footprint_area_m2)} after setbacks, north up.`}
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
            fillOpacity={0.28}
            stroke={FOOTPRINT_COLOR}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
          />
        )}
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
            <title>{`${BOUNDARY_LABELS[e.kind]} limit · ${formatLength(e.length)}`}</title>
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
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-3 rounded-sm border border-dashed"
            style={{
              borderColor: FOOTPRINT_COLOR,
              backgroundColor: `color-mix(in oklch, ${FOOTPRINT_COLOR} 28%, transparent)`,
            }}
          />
          Buildable after setbacks
        </span>
      </figcaption>
    </figure>
  );
}
