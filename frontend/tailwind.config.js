/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        enclave: {
          950: '#0b0f19',
          900: '#111827',
          800: '#1f2937',
          700: '#374151',
          500: '#6366f1',
          400: '#818cf8',
        }
      }
    },
  },
  plugins: [],
}
