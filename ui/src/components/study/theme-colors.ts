import { useMemo, useSyncExternalStore } from "react";

/**
 * three.js cannot parse `oklch()`: theme tokens and data colours are painted
 * on a 1×1 canvas and read back as `rgb()`. Browser only.
 */
let probe: CanvasRenderingContext2D | null = null;

export function toRgb(css: string): string {
  probe ??= document
    .createElement("canvas")
    .getContext("2d", { willReadFrequently: true });
  if (!probe || !css) return css;
  probe.clearRect(0, 0, 1, 1);
  probe.fillStyle = "#000";
  probe.fillStyle = css;
  probe.fillRect(0, 0, 1, 1);
  const [r, g, b] = probe.getImageData(0, 0, 1, 1).data;
  return `rgb(${r}, ${g}, ${b})`;
}

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class", "style", "data-theme"],
  });
  return () => observer.disconnect();
}

const themeKey = () =>
  `${document.documentElement.className}|${document.documentElement.getAttribute("style") ?? ""}`;

export interface SceneColors {
  background: string;
  foreground: string;
  muted: string;
  mutedForeground: string;
  border: string;
}

/** Theme tokens as `rgb()`, refreshed when the root theme class changes. */
export function useSceneColors(): SceneColors {
  const key = useSyncExternalStore(subscribe, themeKey, () => "");
  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const token = (name: string) =>
      toRgb(style.getPropertyValue(`--${name}`).trim());
    return {
      key,
      background: token("background"),
      foreground: token("foreground"),
      muted: token("muted"),
      mutedForeground: token("muted-foreground"),
      border: token("border"),
    };
  }, [key]);
}
