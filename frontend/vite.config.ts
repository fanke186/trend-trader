import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

const apiTarget = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000'
const wsTarget = apiTarget.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      klinecharts: path.resolve(__dirname, '../../KLineChart/src/index.ts')
    }
  },
  server: {
    fs: {
      allow: [path.resolve(__dirname, '..'), path.resolve(__dirname, '../../KLineChart')]
    },
    proxy: {
      '/api': apiTarget,
      '/ws': {
        target: wsTarget,
        ws: true
      }
    }
  }
})
