/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        // Lighter dark ("dark lightish") slate console palette
        ink: {
          950: '#1b212c', // page background
          900: '#202732', // surface
          850: '#252d3a', // raised surface
          800: '#2b3442', // card
          700: '#3a4557', // border strong
          600: '#485468', // border
          400: '#93a0b4', // muted text
          300: '#b0bccd', // secondary text
          100: '#f1f4f9', // primary text
        },
        accent: { DEFAULT: '#38cfe8', dim: '#12809b' },   // cyan — safe actions
        money: { DEFAULT: '#f7b03c', dim: '#a3641a' },     // amber — SAP-posting actions
        ok: { DEFAULT: '#4ade80', dim: '#15803d' },
        bad: { DEFAULT: '#f87171', dim: '#b91c1c' },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
