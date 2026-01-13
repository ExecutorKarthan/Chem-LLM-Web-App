import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  return {
    plugins: [react()],
    server: {
      host: 'localhost',
      port: 32780,
      proxy: {
        '/api': {
          target: mode === 'production' 
            ? 'http://llmexplorer.engr.wustl.edu:8000'
            : 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})