"use client";

import dynamic from "next/dynamic";
import { Box } from "lucide-react";
import type { VerifiedStudy } from "@/lib/study-types";
import { footprintCap, storeyHeight } from "./envelope";
import { formatArea, formatLength, formatVolume } from "./format";

const Volume3D = dynamic(() => import("./volume-3d"), {
  ssr: false,
  loading: () => (
    <div
      role="status"
      className="bg-muted/40 text-muted-foreground flex h-80 w-full animate-pulse items-center justify-center rounded-lg border text-sm"
    >
      Loading 3D view…
    </div>
  ),
});

function Unavailable({ children }: { children: string }) {
  return (
    <div className="bg-muted/30 text-muted-foreground flex items-start gap-2 rounded-lg border border-dashed p-4 text-sm">
      <Box
        aria-hidden
        className="mt-0.5 size-4 shrink-0"
      />
      <p>{children}</p>
    </div>
  );
}

export function VolumePanel({ study }: { study: VerifiedStudy }) {
  const { envelope } = study;
  const params = study.study.envelope;
  const { footprint, max_height_m: height } = envelope;

  if (footprint === null) {
    return (
      <Unavailable>
        Nothing remains of the site once the setbacks are applied, so there is
        no buildable volume to draw.
      </Unavailable>
    );
  }
  if (height === null) {
    return (
      <Unavailable>
        The documents set no height limit, so the volume cannot be drawn. The
        buildable footprint is shown on the site plan.
      </Unavailable>
    );
  }

  const storeys = params.max_storeys.value;
  const cap = footprintCap(envelope, params);
  const shown = envelope.footprint_area_m2 * height;

  return (
    <figure>
      <Volume3D
        site={study.site.polygon}
        footprint={footprint}
        boundaries={study.boundaries}
        maxHeight={height}
        maxStoreys={storeys}
        storeyHeight={storeyHeight(height, storeys)}
      />
      <figcaption className="text-muted-foreground mt-2 text-xs leading-relaxed">
        Shown volume = footprint after setbacks (
        {formatArea(envelope.footprint_area_m2)}) × max height (
        {formatLength(height, 0)}) = {formatVolume(shown)}
        {storeys === null
          ? "; floor lines every 3 m."
          : `; floor lines every ${formatLength(storeyHeight(height, storeys))}.`}
        {cap && envelope.max_volume_m3 !== null && (
          <>
            {" "}
            The {cap} limit caps the buildable area at{" "}
            <span className="text-foreground font-medium">
              {formatArea(envelope.max_footprint_area_m2)}
            </span>
            , so the max volume is{" "}
            <span className="text-foreground font-medium">
              {formatVolume(envelope.max_volume_m3)}
            </span>{" "}
            (the drawn shape is the setback envelope).
          </>
        )}
      </figcaption>
    </figure>
  );
}
