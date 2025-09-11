// Import needed modules
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Define Vite configuration and sets base public path
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',      // Make frontend accessible from outside the container
    port: 32780,
    proxy: {
      '/api': {            // Proxy all /api requests to Django
        target: 'http://llmexplorer.engr.wustl.edu:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});