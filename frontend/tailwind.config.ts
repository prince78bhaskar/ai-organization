import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0d12",
        surface: "#12151c",
        violet: "#7c5cff",
        azure: "#4f8cff",
      },
    },
  },
  plugins: [],
};

export default config;
