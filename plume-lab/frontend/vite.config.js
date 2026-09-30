import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 离线教学应用：不使用任何在线底图瓦片。
// /api 在开发期代理到 FastAPI；构建产物由 FastAPI 直接托管。
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
  },
})
