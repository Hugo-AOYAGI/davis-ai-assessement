"use client";

import {
  Box,
  Building2,
  Car,
  CircleHelp,
  Compass,
  FileText,
  Images,
  Lightbulb,
  ListChecks,
  Map as MapIcon,
  Ruler,
} from "lucide-react";
import { useMemo } from "react";
import type { VerifiedStudy } from "@/lib/study-types";
import { MarkdownText } from "@/components/thread/markdown-text";
import { AdmissibilityList } from "./admissibility";
import { AmbiguityList } from "./ambiguities";
import { CitationChecksContext, indexChecks } from "./citation-checks";
import { EvidenceGallery } from "./evidence-gallery";
import { formatVolume } from "./format";
import { StudyHeader } from "./header";
import { KeyFigures } from "./key-figures";
import { LimitsTable } from "./limits-table";
import { ParkingList } from "./parking";
import { RuleList } from "./rule-list";
import { Section } from "./section";
import { SitePlan } from "./site-plan";
import { VolumePanel } from "./volume-panel";

function verdictMeta(study: VerifiedStudy): string {
  const counts = new Map<string, number>();
  for (const a of study.study.admissibility) {
    counts.set(a.verdict, (counts.get(a.verdict) ?? 0) + 1);
  }
  return [...counts].map(([verdict, n]) => `${n} ${verdict}`).join(" · ");
}

function Assumptions({ study }: { study: VerifiedStudy }) {
  const groups = [
    { title: "Envelope", items: study.envelope.assumptions },
    { title: "Site", items: study.site.choice.assumptions },
  ].filter((g) => g.items.length > 0);
  if (groups.length === 0) {
    return <p className="text-muted-foreground text-sm">None recorded.</p>;
  }
  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g.title}>
          <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
            {g.title}
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-relaxed">
            {g.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** The verified buildability study, as a compact card for the chat column. */
export function StudyView({ study }: { study: VerifiedStudy }) {
  const s = study.study;
  const checks = useMemo(
    () => indexChecks(study.citation_checks),
    [study.citation_checks],
  );
  const limitsSet = Object.values(s.envelope).filter(
    (l) => l.value !== null,
  ).length;
  const byUser = s.ambiguities.filter((a) => a.resolved_by === "user").length;
  const assumptionCount =
    study.envelope.assumptions.length + study.site.choice.assumptions.length;

  return (
    <CitationChecksContext value={checks}>
      <article
        aria-label={`Buildability study for ${s.address}`}
        className="bg-card text-card-foreground w-full overflow-hidden rounded-xl border shadow-sm"
      >
        <StudyHeader study={study} />
        <KeyFigures study={study} />
        <Section
          title="Buildable volume"
          icon={Box}
          meta={
            study.envelope.max_volume_m3 === null
              ? undefined
              : `max ${formatVolume(study.envelope.max_volume_m3)}`
          }
          defaultOpen
        >
          <VolumePanel study={study} />
        </Section>
        <Section
          title="Site plan"
          icon={MapIcon}
          meta={`${study.boundaries.length} limits`}
        >
          <SitePlan study={study} />
        </Section>
        <Section
          title="Summary"
          icon={FileText}
        >
          <div className="text-sm">
            <MarkdownText>{s.summary}</MarkdownText>
          </div>
        </Section>
        <Section
          title="Envelope limits"
          icon={Ruler}
          meta={`${limitsSet} of 7 set`}
        >
          <LimitsTable params={s.envelope} />
        </Section>
        <Section
          title="Admissibility"
          icon={Building2}
          meta={verdictMeta(study)}
        >
          <AdmissibilityList items={s.admissibility} />
        </Section>
        <Section
          title="Parking"
          icon={Car}
          meta={s.parking.length}
        >
          <ParkingList rules={s.parking} />
        </Section>
        <Section
          title="Conditions"
          icon={ListChecks}
          meta={s.conditions.length}
        >
          <RuleList
            rules={s.conditions}
            empty="No other condition."
          />
        </Section>
        {(s.regime.oap_applicable || s.regime.oap_prescriptions.length > 0) && (
          <Section
            title="OAP prescriptions"
            icon={Compass}
            meta={s.regime.oap_prescriptions.length}
          >
            <RuleList
              rules={s.regime.oap_prescriptions}
              empty="The OAP sets no specific prescription for the site."
            />
          </Section>
        )}
        <Section
          title="Ambiguities"
          icon={CircleHelp}
          meta={
            byUser > 0
              ? `${s.ambiguities.length} · ${byUser} by user`
              : s.ambiguities.length
          }
        >
          <AmbiguityList items={s.ambiguities} />
        </Section>
        <Section
          title="Assumptions"
          icon={Lightbulb}
          meta={assumptionCount}
        >
          <Assumptions study={study} />
        </Section>
        <Section
          title="Evidence"
          icon={Images}
          meta={study.evidence.length}
        >
          <EvidenceGallery evidence={study.evidence} />
        </Section>
      </article>
    </CitationChecksContext>
  );
}

export default StudyView;
