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
      },
      borderRadius: {
        "2xl": "16px",
      },
      fontFamily: {
        display: ["Archivo", "Noto Sans SC", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
        sans: ["'Noto Sans SC'", "Archivo", "sans-serif"],
      },
      backgroundImage: {
        // gradient card surface used across BI cards
        card: "linear-gradient(180deg,#151A26,#11151F)",
      },
    },
  },
  plugins: [],
} satisfies Config;
