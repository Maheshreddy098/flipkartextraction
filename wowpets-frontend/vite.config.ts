import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Icons from 'unplugin-icons/vite'
import { getBuildBasePath, getBuildOutDir, getDevServerConfig } from './build.config.js'

export default defineConfig(({ command }) => {
  const base = getBuildBasePath(command)
  const devServer = getDevServerConfig()
  const outDir = getBuildOutDir()

  return {
    base,
    plugins: [
      vue(),
      Icons({ compiler: 'vue3' }),
      {
        name: 'transform-index.html',
        transformIndexHtml(html, context) {
          if (!context.server) {
            return html.replace(
              /<\/body>/,
              `
              <script>
                  {% for key in boot %}
                  window["{{ key }}"] = {{ boot[key] | tojson }};
                  {% endfor %}
              </script>
              </body>
              `
            )
          }
          return html
        },
      },
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    build: {
      outDir: path.resolve(__dirname, outDir),
      emptyOutDir: true,
      sourcemap: true,
    },
    optimizeDeps: {
      include: ['axios'],
    },
    server: {
      port: devServer.PORT,
      host: devServer.HOST,
      // Proxy backend calls to Frappe in dev so the SPA (same-origin to the dev
      // server) reaches the API and cookies without CORS. Target comes from
      // FRAPPE_BACKEND env or DEV_SERVER.BACKEND in src/config/settings.js.
      proxy: {
        '/api': { target: process.env.FRAPPE_BACKEND || devServer.BACKEND, changeOrigin: true, ws: true },
        '/assets': { target: process.env.FRAPPE_BACKEND || devServer.BACKEND, changeOrigin: true },
        '/files': { target: process.env.FRAPPE_BACKEND || devServer.BACKEND, changeOrigin: true },
        '/private': { target: process.env.FRAPPE_BACKEND || devServer.BACKEND, changeOrigin: true },
      },
    },
  }
})
