import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Fiserv brand palette
        brand: {
          50: "#fff7f0",
          100: "#ffecd9",
          200: "#ffd5b3",
          300: "#ffb480",
          400: "#ff9047",
          500: "#FF6200",
          600: "#cc4e00",
          700: "#a33e00",
          800: "#7a2e00",
          900: "#521f00",
        },
        ink: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "IBM Plex Mono", "Consolas", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,98,0,.18), 0 8px 28px -8px rgba(255,98,0,.40)",
        soft: "0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06)",
        lift: "0 6px 16px -4px rgba(15,23,42,.10), 0 2px 6px -2px rgba(15,23,42,.06)",
      },
      backgroundImage: {
        "brand-grad": "linear-gradient(135deg, #FF6200 0%, #ff8c1e 50%, #ffa040 100%)",
        "warm-grad": "linear-gradient(180deg, #fff7f0 0%, #fffaf5 50%, #fff2e6 100%)",
        "sheen": "linear-gradient(135deg, rgba(255,255,255,0.0), rgba(255,255,255,0.25), rgba(255,255,255,0.0))",
      },
      animation: {
        "fade-in": "fadeIn .25s ease-out",
        "slide-up": "slideUp .3s cubic-bezier(.2,.8,.4,1)",
        "shimmer": "shimmer 1.8s linear infinite",
        "pulse-soft": "pulseSoft 2.5s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        shimmer: { "0%": { backgroundPosition: "-400px 0" }, "100%": { backgroundPosition: "400px 0" } },
        pulseSoft: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".55" } },
      },
    },
  },
  plugins: [typography],
};
