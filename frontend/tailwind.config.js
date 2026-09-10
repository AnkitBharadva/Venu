/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        venu: {
          bg: '#F3F1EC',
          surface: '#F8F7F3',
          elevated: '#FCFBF8',
          border: '#D8D5CE',
          'border-strong': '#C7C3BA',
          primary: '#252525',
          secondary: '#6F6D68',
          muted: '#99958D',
          charcoal: '#30302E',
          silver: '#B9B8B3',
          'silver-light': '#D9D8D3',
          orange: '#E8A36A',
          'orange-light': '#F3C49A',
          yellow: '#EBCB72',
          'yellow-light': '#F5DEA0',
          success: '#7E9D82',
          danger: '#C87970',
        }
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        serif: ['Newsreader', 'Georgia', 'Cambria', 'serif'],
      },
      boxShadow: {
        'soft': '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px 0 rgba(0, 0, 0, 0.02)',
        'elevated': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
      }
    },
  },
  plugins: [],
}
