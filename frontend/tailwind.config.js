/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dashboard: {
          bg: '#0f1117',
          card: '#1a1d2e',
          border: '#2a2d3e',
          hover: '#252840',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
