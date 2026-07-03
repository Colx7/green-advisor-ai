import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5010,
    proxy: { '/api': 'http://localhost:8010' }
  }
})
