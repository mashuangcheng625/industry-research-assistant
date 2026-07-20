import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { viteMockServe } from 'vite-plugin-mock'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd()) as {
    VITE_API_BASE: string
    VITE_API_PROXY: string
  }

  return {
    server: {
      port: 5183,
      host: '0.0.0.0',
      proxy: {
        [env.VITE_API_BASE]: env.VITE_API_PROXY,
      },
    },
    resolve: {
      alias: [
        {
          find: /^@\//,
          replacement: '/src/',
        },
      ],
    },

    build: {
      // Route-level splitting is defined with React.lazy in router/routes.tsx.
      // Keep only the large, isolated charting stack in a manual chunk. Splitting
      // React, Ant Design and their shared helpers into separate manual chunks
      // creates a circular ESM dependency and can crash before React mounts.
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) {
              return 'vendor-echarts'
            }
          },
        },
      },
    },

    plugins: [
      react(),
      viteMockServe({
        enable: false,
      }),
    ],
  }
})
