/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scan every HTML file and every JS file in static/ for class usage.
  // The concept-*.html files use vanilla Tailwind with no custom classes,
  // so they are included here to ensure their utility classes are retained.
  content: [
    './static/**/*.html',
    './static/**/*.js',
    './src/**/*.py',        // FastAPI Jinja2 templates rendered server-side
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#1a1b4b',
          light:   '#252662',
          dark:    '#12133a',
          card:    '#1e2055',
        },
        coral: {
          DEFAULT: '#f95c5c',
          dark:    '#e04444',
          light:   '#ff7a7a',
        },
        slate: {
          // Tailwind already ships a full slate palette; this adds the
          // project-specific chat shade without overwriting the defaults.
          chat: '#2a2d6b',
        },
      },
      fontFamily: {
        // System font stack — no external font loading, GDPR-safe.
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'system-ui',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
};
