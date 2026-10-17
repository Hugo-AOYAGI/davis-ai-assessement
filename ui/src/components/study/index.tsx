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
  Maximize2,
  PencilRuler,
  Ruler,
} from "lucide-react";
import { useMemo } from "react";
import type { EnvelopeStudy, VerifiedStudy } from "@/lib/study-types";
import { MarkdownText } from "@/components/thread/markdown-text";
import { AdmissibilityList } from "./admissibility";
import { AmbiguityList } from "./ambiguities";
import { CitationChecksContext, indexChecks } from "./citation-checks";
import { findBound, readEnvelope } from "./envelope";
import { EvidenceGallery } from "./evidence-gallery";
import { formatVolume } from "./format";
import { StudyHeader } from "./header";
import { KeyFigures } from "./key-figures";
import { LimitsTable } from "./limits-table";
import { ParkingList } from "./parking";
import { RuleList } from "./rule-list";
import { BoundsList, ProposalView } from "./scenarios";
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

/** Assumptions by origin, each listed once (bounds often repeat theirs). */
function assumptionGroups(
  study: VerifiedStudy,
  envelope: EnvelopeStudy | null,
) {
  const seen = new Set<string>();
  const once = (items: string[]) =>
    items.filter((item) => !seen.has(item) && seen.add(item));
  return [
    { title: "Proposal", items: once(envelope?.proposal.assumptions ?? []) },
    {
      title: "Bounds",
      items: once(envelope?.bounds.flatMap((b) => b.assumptions) ?? []),
    },
    { title: "Site", items: once(study.site.choice.assumptions) },
  ].filter((g) => g.items.length > 0);
}

function Assumptions({
  groups,
}: {
  groups: { title: string; items: string[] }[];
}) {
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

function proposalMeta(envelope: EnvelopeStudy): string {
  const { proposal } = envelope;
  if (!proposal.fits) return "does not fit";
  const n = proposal.buildings.length;
  return n === 0
    ? "no building"
    : `${n} building${n > 1 ? "s" : ""} · ${formatVolume(proposal.total_volume_m3)}`;
}

/** The verified buildability study, as a compact card for the chat column. */
export function StudyView({ study }: { study: VerifiedStudy }) {
  const s = study.study;
  const checks = useMemo(
    () => indexChecks(study.citation_checks),
    [study.citation_checks],
  );
  const envelope = readEnvelope(study);
  const known = useMemo(
    () => [
      ...(envelope?.rules.buildings.map((b) => b.building) ?? []),
      ...s.admissibility.map((a) => a.building),
    ],
    [envelope, s.admissibility],
  );
  const largest = envelope ? findBound(envelope, "largest") : undefined;
  const byUser = s.ambiguities.filter((a) => a.resolved_by === "user").length;
  const assumptions = assumptionGroups(study, envelope);
  const assumptionCount = assumptions.reduce((n, g) => n + g.items.length, 0);

  return (
    <CitationChecksContext value={checks}>
      <article
        aria-label={`Buildability study for ${s.address}`}
        className="bg-card text-card-foreground w-full overflow-hidden rounded-xl border shadow-sm"
      >
        <StudyHeader study={study} />
        <KeyFigures
          study={study}
          envelope={envelope}
        />
        <Section
          title="Buildable volume"
          icon={Box}
          meta={envelope ? proposalMeta(envelope) : undefined}
          defaultOpen
        >
          {envelope ? (
            <VolumePanel
              study={study}
              envelope={envelope}
            />
          ) : (
            <p className="text-muted-foreground text-sm">
              This study has no envelope with bounds and a proposal: it was
              produced before they existed.
            </p>
          )}
        </Section>
        <Section
          title="Site plan"
          icon={MapIcon}
          meta={`${study.boundaries.length} limits`}
        >
          <SitePlan
            study={study}
            envelope={envelope}
          />
        </Section>
        <Section
          title="Summary"
          icon={FileText}
        >
          <div className="text-sm">
            <MarkdownText>{s.summary}</MarkdownText>
          </div>
        </Section>
        {envelope && (
          <>
            <Section
              title="Proposal"
              icon={PencilRuler}
              meta={proposalMeta(envelope)}
            >
              <ProposalView
                envelope={envelope}
                known={known}
              />
            </Section>
            <Section
              title="Bounds"
              icon={Maximize2}
              meta={
                largest
                  ? `max ${formatVolume(largest.total_volume_m3)}`
                  : envelope.bounds.length
              }
            >
              <BoundsList
                envelope={envelope}
                known={known}
              />
            </Section>
            <Section
              title="Envelope rules"
              icon={Ruler}
              meta={`${envelope.rules.setbacks.length} edge kinds · ${envelope.rules.buildings.length} buildings`}
            >
              <LimitsTable rules={envelope.rules} />
            </Section>
          </>
        )}
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
          <Assumptions groups={assumptions} />
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
