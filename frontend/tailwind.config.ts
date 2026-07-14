import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // BI design tokens v2 (matches frontend/design/overview-mockup.html)
        bg: "#090C12",
        panel: "#11151F",
        panel2: "#151A26",
        line: "#232B3C",
        text: "#EAEDF3",
        muted: "#8A93A8",
        dim: "#5C6579",
        lime: "#B6FF3C",
        cyan: "#4CD4F0",
        violet: "#A78BFA",
        pink: "#FF6FB5",
        good: "#38E08A",
        warn: "#FFB020",
        alert: "#FF5C7A",
        // keep `accent` alias so any lingering references still resolve to the lime
        accent: "#B6FF3C",
        // glass design tokens (direction B) — appended, keeps BI colors above
        blue1: "#2f7bff",
        blue2: "#5ca8ff",
        run: "#4CD4F0",
        ok: "#38E08A",
        block: "#FFB020",
        err: "#FF5C7A",
        txt: "#EAF0FA",
        muted2: "#93A0B8",
        dim2: "#5C6579",
      },
      borderRadius: {
        "2xl": "16px",
      },
      fontFamily: {
        display: ["Archivo", "Noto Sans SC", "sans-serif"],
        sans: ["Inter", "Noto Sans SC", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      backgroundImage: {
        // gradient card surface used across BI cards
        card: "linear-gradient(180deg,#151A26,#11151F)",
      },
    },
  },
  plugins: [],
} satisfies Config;
