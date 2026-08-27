import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
  base: env.VITE_BASE_PATH || '/',
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@sau': fileURLToPath(new URL('./src/modules/sau', import.meta.url)),
      '@commander': fileURLToPath(new URL('./src/modules/commander', import.meta.url)),
    },
  },
  css: {
    preprocessorOptions: {
      scss: {},
    },
  },
  server: {
    host: true,
    port: 5174,
    strictPort: true,
    proxy: {
      // CrossHub Java（优先 127.0.0.1，避免 localhost→IPv6 偶发 502）
      ...Object.fromEntries(
        [
          '/api/temu',
          '/api/auth',
          '/api/warehouse',
          '/api/tenant',
          '/api/platform-accounts',
          '/api/platform',
          '/api/aliexpress',
          '/api/monitor',
          '/api/tasks',
          '/api/ops-feedback',
          '/api/amazon',
          '/api/douyin',
          '/api/1688',
          '/api/pdd',
          '/api/agent',
          '/api/sau',
          '/api/commander',
          '/api/ai-image',
          '/api/health',
        ].map((path) => [
          path,
          {
            target: env.VITE_TEMU_API_PROXY || 'http://127.0.0.1:18080',
            changeOrigin: true,
          },
        ]),
      ),
      // 自媒体 SAU：默认直连 https://automedia.yoto.work/api（见 modules/sau/utils/apiBase.js），
      // 不再经本机 /sau-api → :5409。仅当显式设置 VITE_SAU_API_PROXY 时才启用本地反代调试。
      ...(env.VITE_SAU_API_PROXY
        ? {
            '/sau-api': {
              target: env.VITE_SAU_API_PROXY,
              changeOrigin: true,
              rewrite: (path) => path.replace(/^\/sau-api/, ''),
            },
          }
        : {}),
      // AI 生图：本站前端自写；/api-proxy → 线上同款生图上游（须写在通用 /api 之前）
      '/api-proxy': {
        target: env.VITE_GPT_IMAGE_PROXY_TARGET || 'https://api.hyhacct.com',
        changeOrigin: true,
        secure: true,
        timeout: 600_000,
        proxyTimeout: 600_000,
        rewrite: (path) => path.replace(/^\/api-proxy/, '/v1'),
      },
      // Commander Go API（自动上货等）；须写在通用 /api 之前，避免落到 Express
      '/api/v1': {
        target: env.VITE_COMMANDER_API_PROXY || 'https://www.yoto.work',
        changeOrigin: true,
        secure: true,
        timeout: 300_000,
        proxyTimeout: 300_000,
      },
      // 其余历史 Demo API → Express
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true,
    port: 4173,
  },
}})
