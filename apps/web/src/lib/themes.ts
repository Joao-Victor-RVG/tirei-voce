import type { CSSProperties } from "react";

export type ThemeStyle = {
  accent: string;
  accentSoft: string;
  accentText: string;
  tagline: string;
};

const THEMES: Record<string, ThemeStyle> = {
  "amigo-secreto": {
    accent: "#e11d48",
    accentSoft: "#ffe4e6",
    accentText: "#9f1239",
    tagline: "Quem será que te tirou?",
  },
  "amigo-da-onca": {
    accent: "#d97706",
    accentSoft: "#fef3c7",
    accentText: "#92400e",
    tagline: "Prepare o presente mais duvidoso do ano!",
  },
  "amigo-calcinha": {
    accent: "#c026d3",
    accentSoft: "#fae8ff",
    accentText: "#86198f",
    tagline: "Conforto, estilo e muita risada.",
  },
};

export function themeStyle(slug: string | undefined): ThemeStyle {
  return THEMES[slug ?? ""] ?? THEMES["amigo-secreto"]!;
}

/** Variáveis CSS usadas pelas classes `bg-(--accent)`, `text-(--accent-text)` etc. */
export function themeVars(slug: string | undefined): CSSProperties {
  const theme = themeStyle(slug);
  return {
    "--accent": theme.accent,
    "--accent-soft": theme.accentSoft,
    "--accent-text": theme.accentText,
  } as CSSProperties;
}
