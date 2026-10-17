import { useEffect, useState } from "react";

/**
 * Recharts needs literal color strings, so the semantic tokens of
 * `src/index.css` are read off `<html>` with `getComputedStyle` and re-read
 * whenever the theme class changes. The fallbacks keep the charts readable if
 * the variables are missing (e.g. during a hydration hiccup).
 */
export type ChartColors = {
  success: string;
  danger: string;
  primary: string;
  muted: string;
  text: string;
  surface: string;
  border: string;
  /** Translucent fills for the bar hover cursor and donut tracks. */
  cursor: string;
};

const FALLBACK_TRIPLES: Record<string, string> = {
  "--color-success": "5 150 105",
  "--color-danger": "220 38 38",
  "--color-primary": "15 118 110",
  "--color-muted": "100 116 139",
  "--color-text": "15 23 42",
  "--color-surface": "255 255 255",
  "--color-border": "226 232 240",
};

function triple(name: string): string {
  if (typeof document === "undefined") return FALLBACK_TRIPLES[name];
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return raw || FALLBACK_TRIPLES[name];
}

function rgb(name: string, alpha = 1): string {
  const value = triple(name);
  return alpha >= 1 ? `rgb(${value})` : `rgb(${value} / ${alpha})`;
}

export function readChartColors(): ChartColors {
  return {
    success: rgb("--color-success"),
    danger: rgb("--color-danger"),
    primary: rgb("--color-primary"),
    muted: rgb("--color-muted"),
    text: rgb("--color-text"),
    surface: rgb("--color-surface"),
    border: rgb("--color-border"),
    cursor: rgb("--color-muted", 0.12),
  };
}

/**
 * Theme-aware chart palette.
 *
 * It watches the `class` attribute of `<html>` instead of the theme store:
 * the store changes one render before `useTheme` writes the class, and reading
 * the variables too early would hand recharts the previous theme's colors.
 */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(readChartColors);

  useEffect(() => {
    const root = document.documentElement;
    setColors(readChartColors());
    const observer = new MutationObserver(() => setColors(readChartColors()));
    observer.observe(root, { attributes: true, attributeFilter: ["class", "style"] });
    return () => observer.disconnect();
  }, []);

  return colors;
}
