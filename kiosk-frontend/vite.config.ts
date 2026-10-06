import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import path from 'path'
import { VitePWA } from 'vite-plugin-pwa'
import frappeui from 'frappe-ui/vite'
import Icons from 'unplugin-icons/vite'
import { getBuildBasePath, getBuildOutDir, getDevServerConfig } from './build.config.js'

// https://vitejs.dev/config/
export default defineConfig(({ mode, command }) => {
  // Get configuration from centralized kiosk.settings.js
  const base = getBuildBasePath(command)
  const devServer = getDevServerConfig()
  const outDir = getBuildOutDir()

  return {
    base,
  plugins: [
    frappeui({
      buildConfig: {
        outDir: path.resolve(__dirname, outDir),
        indexHtmlPath: path.resolve(__dirname, outDir, 'index.html'),
      },
    }),
    Icons({
      compiler: 'vue3',
    }),
    vue({
      script: {
        propsDestructure: true,
      },
    }),
    vueJsx(),
    VitePWA({
      registerType: "autoUpdate",
      devOptions: {
        enabled: true,
      },
      manifest: {
        display: "fullscreen",
        name: "Khanal Foods Kiosk",
        short_name: "KFL Kiosk",
        start_url: base.replace(/\/$/, ''),
        description: "Production Kiosk Tool for Khanal Foods",
        orientation: "landscape",
        theme_color: "#1f2937",
        background_color: "#ffffff",
        icons: [
          {
            src: "icons/icon.svg",
            sizes: "192x192",
            type: "image/svg+xml",
            purpose: "any maskable",
          },
          {
            src: "icons/icon.svg",
            sizes: "512x512",
            type: "image/svg+xml",
            purpose: "any maskable",
          }
        ],
      },
      workbox: {
        maximumFileSizeToCacheInBytes: 3000000, // 3MB
        globPatterns: [
          '**/*.{js,css,html,ico,png,jpg,jpeg,svg,woff,woff2}'
        ]
      }
    }),
    {
      name: "transform-index.html",
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
          );
        }
        return html;
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, outDir),
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunks for better caching
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'ui-vendor': ['lucide-vue-next'],
          'axios-vendor': ['axios']
        }
      }
    },
    cssCodeSplit: true,
    // Optimize CSS
    cssMinify: 'esbuild',
    // Improve build performance
    chunkSizeWarningLimit: 1000,
    commonjsOptions: {
      include: [/tailwind.config.js/, /node_modules/],
    },
  },
  optimizeDeps: {
    include: [
      "feather-icons",
      "tailwind.config.js",
      "engine.io-client",
      "qrcode",
      "axios",
    ],
  },
  server: {
    port: devServer.PORT,
    host: devServer.HOST,
    cors: true,
    hmr: {
      overlay: false
    }
  },
  preview: {
    port: devServer.PORT,
    host: devServer.HOST,
  },
}
})
