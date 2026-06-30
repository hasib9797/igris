/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ember: {
          50: "#f6f1ff",
          100: "#ede2ff",
          200: "#d9c0ff",
          300: "#bf91ff",
          400: "#a362ff",
          500: "#8b3dff",
          600: "#7524f3",
          700: "#5f18c7",
          800: "#46158d",
          900: "#2b1056"
        }
      },
      fontFamily: {
        display: ["ui-serif", "Georgia", "serif"],
        sans: ["ui-sans-serif", "system-ui", "sans-serif"]
      },
      boxShadow: {
        panel: "0 28px 90px rgba(5, 2, 17, 0.58)"
      },
      backgroundImage: {
        "igris-glow": "radial-gradient(circle at top, rgba(139,61,255,0.30), transparent 34%), radial-gradient(circle at 18% 18%, rgba(108,40,217,0.18), transparent 26%), linear-gradient(135deg, #090611 0%, #120b22 46%, #05040a 100%)"
      }
    },
  },
  plugins: [],
};
