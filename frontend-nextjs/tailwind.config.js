/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'bg-deep': '#060b18',
        'bg-dark': '#0d1526',
        'bg-card': '#111d35',
        'bg-glass': 'rgba(17, 29, 53, 0.7)',
        'border': 'rgba(99, 102, 241, 0.18)',
        'border-glow': 'rgba(99, 102, 241, 0.5)',
        'indigo': '#6366f1',
        'indigo-light': '#818cf8',
        'cyan': '#22d3ee',
        'amber': '#f59e0b',
        'emerald': '#10b981',
        'rose': '#f43f5e',
        'violet': '#a78bfa',
        'text-1': '#f1f5f9',
        'text-2': '#94a3b8',
        'text-3': '#64748b',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'radius': '14px',
        'radius-sm': '8px',
      },
      boxShadow: {
        'glow-indigo': '0 0 40px rgba(99,102,241,0.15)',
      },
    },
  },
  plugins: [],
};