/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ember: {
          50: "#fff5f2",
          100: "#ffe6dc",
          200: "#ffc7af",
          300: "#ff9e77",
          400: "#ff6b47",
          500: "#f8421f",
          600: "#d62b0e",
          700: "#a91e0c",
          800: "#7f1a12",
          900: "#45110d"
        }
      },
      fontFamily: {
        display: ["ui-serif", "Georgia", "serif"],
        sans: ["ui-sans-serif", "system-ui", "sans-serif"]
      },
      boxShadow: {
        panel: "0 24px 80px rgba(0,0,0,0.45)"
      },
      backgroundImage: {
        "igris-glow": "radial-gradient(circle at top, rgba(248,66,31,0.24), transparent 35%), linear-gradient(135deg, #0f1115 0%, #171a20 45%, #0a0b0d 100%)"
      }
    },
  },
  plugins: [],
};
