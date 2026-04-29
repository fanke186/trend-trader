import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const apiTarget = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8001'
const wsTarget = apiTarget.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom'
  },
  server: {
    proxy: {
      '/api': apiTarget,
      '/ws': {
        target: wsTarget,
        ws: true
      }
    }
  }
})
