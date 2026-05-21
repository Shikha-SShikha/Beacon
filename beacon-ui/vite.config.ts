import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
const API_ROUTES = [
  '/institutions', '/search', '/ask', '/journals',
  '/baseline', '/citation', '/collections', '/attribution',
  '/analytics', '/health',
];

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      API_ROUTES.map(route => [route, { target: 'http://localhost:8000', changeOrigin: true }])
    ),
  },
})
