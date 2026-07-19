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
      // P1-10: route-level splitting via React.lazy (see router/routes.tsx)
      // is complemented by vendor splitting so the initial entry chunk
      // shrinks to ~300 KB while antd / react / echarts stay in their
      // own cacheable bundles.
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (id.includes('node_modules/antd') || id.includes('node_modules/@ant-design')) {
              return 'vendor-antd'
            }
            if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/scheduler')) {
              return 'vendor-react'
            }
            if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) {
              return 'vendor-echarts'
            }
            if (id.includes('node_modules')) {
              return 'vendor-libs'
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
