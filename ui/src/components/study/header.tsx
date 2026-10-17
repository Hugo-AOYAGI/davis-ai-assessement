import {
  FileCheck2,
  Layers,
  MapPin,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { VerifiedStudy } from "@/lib/study-types";
import { summariseChecks } from "./citation-checks";
import { Pill } from "./pill";

export function StudyHeader({ study }: { study: VerifiedStudy }) {
  const { regime, address, program } = study.study;
  const parcels = study.site.choice.parcel_ids;
  const overlays = regime.overlays.filter((o) => o.applies);
  const checks = summariseChecks(study.citation_checks);
  const allVerified = checks.verified === checks.checkable;
  const verificationTitle = [
    `${checks.verified} of ${checks.checkable} quoted passages found verbatim in the documents`,
    checks.raster > 0 &&
      `${checks.raster} citation(s) of image-only documents not text-checked`,
  ]
    .filter(Boolean)
    .join("; ");

  return (
    <header className="space-y-3 px-4 pt-4 pb-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
            Buildability study
          </p>
          <h2 className="mt-0.5 flex items-start gap-1.5 text-base leading-snug font-semibold">
            <MapPin
              aria-hidden
              className="text-muted-foreground mt-0.5 size-4 shrink-0"
            />
            {address}
          </h2>
        </div>
        <Pill
          tone={allVerified ? "positive" : "caution"}
          title={verificationTitle}
          className="mt-0.5"
        >
          {allVerified ? (
            <ShieldCheck aria-hidden />
          ) : (
            <ShieldAlert aria-hidden />
          )}
          <span className="sr-only">Citations verified: </span>
          {checks.verified}/{checks.checkable} verified
        </Pill>
      </div>
      <p className="text-muted-foreground text-sm leading-relaxed">{program}</p>
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill
          tone="info"
          title="Zone of the local plan (PLU)"
        >
          <Layers aria-hidden />
          Zone {regime.zone}
        </Pill>
        {regime.oap_applicable && (
          <Pill
            tone="caution"
            title="A development orientation (OAP) covers the site: the project must be compatible with it"
          >
            <FileCheck2 aria-hidden />
            OAP applies
          </Pill>
        )}
        {overlays.map((o) => (
          <Pill
            key={o.item}
            tone="outline"
            title={o.note}
            className="max-w-full truncate"
          >
            {o.item}
          </Pill>
        ))}
        <span className="text-muted-foreground ml-auto font-mono text-[11px]">
          {parcels.length > 1 ? "Parcels " : "Parcel "}
          {parcels.join(", ")}
        </span>
      </div>
    </header>
  );
}
