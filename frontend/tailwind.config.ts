/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Noto Sans SC",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "Cascadia Code",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        bg: {
          base: "#0a0a0f",
          panel: "#111118",
          surface: "#1a1a24",
          elevated: "#22222e",
        },
        border: {
          DEFAULT: "#2a2a38",
          accent: "#3a3a50",
        },
        accent: {
          cyan: "#00d4d4",
          magenta: "#d400d4",
          green: "#00d400",
          yellow: "#d4d400",
          blue: "#0044d4",
          red: "#d40000",
        },
      },
    },
  },
  plugins: [],
};
