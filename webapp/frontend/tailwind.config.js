/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Manrope", "sans-serif"],
        body: ["Public Sans", "sans-serif"]
      },
      colors: {
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
