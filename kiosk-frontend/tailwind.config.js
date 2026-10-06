module.exports = {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  safelist: [
    { pattern: /!(text|bg)-/, variants: ['hover', 'active'] },
    { pattern: /^grid-cols-/ },
  ],
  theme: {
    extend: {
      colors: {
        'khanal': {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        'kiosk': {
          primary: '#1f2937',
          secondary: '#374151',
          accent: '#f59e0b',
          success: '#10b981',
          warning: '#f59e0b',
          error: '#ef4444',
        }
      },
      fontFamily: {
        'kiosk': ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'kiosk-xs': '0.75rem',
        'kiosk-sm': '0.875rem',
        'kiosk-base': '1rem',
        'kiosk-lg': '1.125rem',
        'kiosk-xl': '1.25rem',
        'kiosk-2xl': '1.5rem',
        'kiosk-3xl': '1.875rem',
        'kiosk-4xl': '2.25rem',
        'kiosk-5xl': '3rem',
      },
      spacing: {
        'kiosk': '1rem',
        'kiosk-lg': '1.5rem',
        'kiosk-xl': '2rem',
      }
    },
  },
  plugins: [],
}
