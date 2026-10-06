import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// Build output goes into the Frappe app's public folder, served under
// /assets/khanal_tech_integrations/amazonus/. The www/amazonus.html shell is
// regenerated from the built index.html by scripts/sync-html.mjs.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/assets/khanal_tech_integrations/amazonus/' : '/',
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  build: {
    outDir: path.resolve(__dirname, '../khanal_tech_integrations/public/amazonus'),
    emptyOutDir: true,
  },
  server: {
    port: 5175,
    proxy: {
      '/api': { target: 'http://dev.localhost:8000', changeOrigin: false },
    },
  },
  test: {
    environment: 'happy-dom',
  },
}))
