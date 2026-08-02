/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#16302b",
        teal: {
          50: "#effcf8",
          100: "#d8f7ee",
          600: "#0f766e",
          700: "#0d5f59",
        },
        saffron: "#d97706",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(22, 48, 43, 0.08)",
      },
    },
  },
  plugins: [],
};