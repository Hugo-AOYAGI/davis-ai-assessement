import { StudyView } from "@/components/study";
import type { VerifiedStudy } from "@/lib/study-types";

/**
 * Rendered in the conversation right after `submit_study` accepted the study, with
 * `values.artifacts?.study` (the full `VerifiedStudy`).
 */
export function StudySlot({ study }: { study: unknown }) {
  if (!study) return null;
  return <StudyView study={study as VerifiedStudy} />;
}
