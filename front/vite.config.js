import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const VITE_DEV_ORIGIN = 'http://localhost:5173'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/dist/' : '/',
  server: {
    origin: VITE_DEV_ORIGIN,
    port: Number(new URL(VITE_DEV_ORIGIN).port)
  },
  plugins: [vue()],
  define: {
    __BUNDLED_DEV__: 'false',
    __SERVER_FORWARD_CONSOLE__: 'false'
  },
  css: {
    lightningcss: {
      errorRecovery: true
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    manifest: true,
    outDir: '../static/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: '/src/main.js'
    }
  }
}))
