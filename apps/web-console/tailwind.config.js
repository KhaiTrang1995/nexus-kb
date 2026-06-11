/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Match dark aesthetic from root index.html
        'kb-dark': '#07070c',
        'kb-surface': '#0f0f18',
        'kb-card': 'rgba(20, 20, 32, 0.65)',
        'kb-primary': '#6366f1',
        'kb-muted': '#9ca3af',
        'kb-text': '#f3f4f6',
        // For glow if used in future color classes
        'kb-primary-glow': 'rgba(99, 102, 241, 0.45)',
      }
    },
  },
  plugins: [],
}