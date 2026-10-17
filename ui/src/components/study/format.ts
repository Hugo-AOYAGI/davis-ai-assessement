const formatters = new Map<number, Intl.NumberFormat>();

/** French grouping (`5 952`) and decimal comma, at most `digits` decimals. */
export function formatNumber(value: number, digits = 0): string {
  let formatter = formatters.get(digits);
  if (!formatter) {
    formatter = new Intl.NumberFormat("fr-FR", {
      maximumFractionDigits: digits,
    });
    formatters.set(digits, formatter);
  }
  return formatter.format(value);
}

export const formatArea = (m2: number) => `${formatNumber(m2)} m²`;
export const formatVolume = (m3: number) => `${formatNumber(m3)} m³`;
export const formatLength = (m: number, digits = 1) =>
  `${formatNumber(m, digits)} m`;
export const formatPercent = (ratio: number) =>
  `${formatNumber(ratio * 100, 1)} %`;

/** Storeys above ground, ground floor included: 6 → `R+5`. */
export const formatStoreys = (storeys: number) =>
  `R+${formatNumber(Math.max(storeys - 1, 0))}`;

const DOC_LABELS: Record<string, string> = {
  plu_reglement: "PLU",
  plu_reglement_graphique: "Zoning plan",
  oap: "OAP",
};

/** Short, human label for a corpus document id. */
export const docLabel = (doc: string) => DOC_LABELS[doc] ?? doc;

export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
