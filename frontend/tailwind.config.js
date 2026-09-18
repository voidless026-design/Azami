/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#0b0f14",
          1: "#11161d",
          2: "#171e27",
          3: "#1e2732",
        },
        accent: {
          DEFAULT: "#34d399",
          dim: "#0f766e",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        pulseDot: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.3" } },
      },
      animation: { pulseDot: "pulseDot 1.2s ease-in-out infinite" },
    },
  },
  plugins: [],
};
