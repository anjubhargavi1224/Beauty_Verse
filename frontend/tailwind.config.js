/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        urbanist: ["Urbanist", "sans-serif"],
      },
      animation: {
        gloss: "glossy 2s ease-in-out infinite",
      },
      keyframes: {
        glossy: {
          "0%": { transform: "translateX(-100%) rotate(12deg)" },
          "100%": { transform: "translateX(100%) rotate(12deg)" },
        },
      },
    },
  },
  plugins: [],
};
