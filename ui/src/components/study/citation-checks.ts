import { createContext, useContext } from "react";
import type { Citation, CitationCheck } from "@/lib/study-types";

const normalise = (text: string) => text.replace(/\s+/g, " ").trim();

const citationKey = (c: Citation) =>
  `${c.doc}\u0000${c.page ?? ""}\u0000${normalise(c.quote)}`;

export type CheckIndex = Map<string, CitationCheck>;

/** Index of the gate's checks, keyed by doc, page and quote. */
export function indexChecks(checks: CitationCheck[]): CheckIndex {
  return new Map(checks.map((check) => [citationKey(check.citation), check]));
}

export const CitationChecksContext = createContext<CheckIndex>(new Map());

/** The gate's check for a citation (matched by doc, page and quote), if any. */
export function useCitationCheck(
  citation: Citation,
): CitationCheck | undefined {
  return useContext(CitationChecksContext).get(citationKey(citation));
}

export interface VerificationSummary {
  verified: number;
  /** Citations whose text could be checked. */
  checkable: number;
  /** Citations of raster documents, not text-checked. */
  raster: number;
}

export function summariseChecks(checks: CitationCheck[]): VerificationSummary {
  const checkable = checks.filter((c) => c.text_verifiable);
  return {
    verified: checkable.filter((c) => c.verified).length,
    checkable: checkable.length,
    raster: checks.length - checkable.length,
  };
}
