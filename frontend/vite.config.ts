import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

// 백엔드 URL: 환경변수 BACKEND_URL 로 덮어쓸 수 있음
// 예) BACKEND_URL=http://localhost:8001 npm run dev
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8007'

// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), vue(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5177,
    strictPort: false, // 포트 사용 중이면 자동으로 다음 빈 포트 사용
    proxy: {
      '/api': { target: BACKEND_URL, changeOrigin: true },
      '/health': { target: BACKEND_URL, changeOrigin: true },
    },
  },
})
