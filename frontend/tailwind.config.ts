import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base: { 950: '#02040a', 900: '#0a0d14', 850: '#131720', 800: '#1a1f2e' },
        up: '#00d4aa',
        down: '#ff4757',
        warn: '#fbbf24',
        info: '#38bdf8',
        primary: { DEFAULT: '#00d4aa', foreground: '#02040a' },
        accent: { DEFAULT: '#6c5ce7', foreground: '#ffffff' }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace']
      }
    }
  },
  plugins: []
} satisfies Config
