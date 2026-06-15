/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0a0e14",
          900: "#0a0e14",
          800: "#131820",
          700: "#1a2230",
          600: "#1f2937",
        },
        muted: "#6b7280",
        line: "#1f2937",
        up: "#10b981",
        down: "#ef4444",
        amber: "#f59e0b",
        cyan: "#60a5fa",
      },
      fontFamily: {
        sans: ['Pretendard Variable', 'Pretendard', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['Pretendard Variable', 'Pretendard', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['10px', '14px'],
        'xxs': ['11px', '15px'],
      },
    },
  },
  plugins: [],
};
