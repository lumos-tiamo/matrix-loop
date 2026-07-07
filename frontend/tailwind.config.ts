import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0E14",
        panel: "#12161F",
        line: "#232A38",
        text: "#E6E9EF",
        muted: "#8B93A7",
        accent: "#B6FF3C",
        good: "#3ECF8E",
        warn: "#F5A524",
        alert: "#F0526B",
      },
      fontFamily: {
        display: ["Archivo", "Noto Sans SC", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
        sans: ["'Noto Sans SC'", "Archivo", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
