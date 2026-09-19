/** @type {import('tailwindcss').Config} */

/** Semantic token -> CSS variable holding an "R G B" triple (see src/index.css). */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Manrope", "sans-serif"],
        body: ["Public Sans", "sans-serif"]
      },
      colors: {
        // ── Semantic tokens (theme-aware, light + dark) ──────────────────────
        bg: token("color-bg"),
        surface: token("color-surface"),
        surfaceAlt: token("color-surface-alt"),
        text: token("color-text"),
        muted: token("color-muted"),
        border: token("color-border"),
        primary: token("color-primary"),
        primaryFg: token("color-primary-fg"),
        success: token("color-success"),
        warning: token("color-warning"),
        danger: token("color-danger"),

        // ── Fixed brand ramp, for accents only ───────────────────────────────
        brand: {
          50:  "#f2f9f7",
          100: "#d8efe8",
          200: "#b0ddd3",
          300: "#7ec4b8",
          400: "#43a89c",
          500: "#0f766e",
          600: "#0d6360",
          700: "#0f4d48",
          800: "#0c3b37",
          900: "#0b2c29"
        },
        accent: "#f59e0b"
      }
    }
  },
  plugins: []
};
