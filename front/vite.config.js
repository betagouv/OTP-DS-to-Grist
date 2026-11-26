import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// Origine du serveur de dev, partagée avec Flask par le .env racine : lue ici
// pour la config seulement, elle n'est pas exposée au client (envDir inchangé).
// Obligatoire pour le serveur de dev : la page est servie par Flask, et sans
// origine, les URL des assets importés par le CSS (polices du DSFR) partiraient
// vers Flask (404).
const devServer = (mode) => {
  const { VITE_DEV_ORIGIN } = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), '')
  if (!VITE_DEV_ORIGIN) {
    throw new Error('VITE_DEV_ORIGIN manquante dans le .env racine (voir .env.example)')
  }

  // Sans port explicite (URL publique d'un Codespace), Vite garde le sien
  const { port } = new URL(VITE_DEV_ORIGIN)

  return port ? { origin: VITE_DEV_ORIGIN, port: Number(port) } : { origin: VITE_DEV_ORIGIN }
}

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => ({
  base: command === 'build' ? '/static/dist/' : '/',
  server: command === 'serve' ? devServer(mode) : {},
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
