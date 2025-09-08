// Import needed modules
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Define Vite configuration and sets base public path
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',      // Make frontend accessible from outside the container
    port: 5173,
    proxy: {
      '/api': {            // Proxy all /api requests to Django
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});