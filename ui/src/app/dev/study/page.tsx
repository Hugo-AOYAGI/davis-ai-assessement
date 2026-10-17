import { StudyView } from "@/components/study";
import type { VerifiedStudy } from "@/lib/study-types";
import fixture from "@/fixtures/verified_study.json";
import { ThemeFromQuery } from "./theme-from-query";

const study = fixture as unknown as VerifiedStudy;

/** Dev preview of the study card in a chat-width column. `?theme=dark` for dark mode. */
export default function StudyPreviewPage() {
  return (
    <main className="bg-background min-h-screen px-4 py-8">
      <ThemeFromQuery />
      <div className="mx-auto w-full max-w-3xl">
        <StudyView study={study} />
      </div>
    </main>
  );
}
