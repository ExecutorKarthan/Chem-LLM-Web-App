import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, existsSync } from 'fs'
import { resolve } from 'path'

// Plugin to copy RDKit WASM into dist root after every build,
// so Django can serve it at /RDKit_minimal.wasm without it being
// intercepted by the SPA catchall route.
const copyRdkitWasm = () => ({
  name: 'copy-rdkit-wasm',
  closeBundle() {
    const src = resolve(
      __dirname,
      'node_modules/@rdkit/rdkit/dist/RDKit_minimal.wasm'
    )
    const dest = resolve(__dirname, 'dist/RDKit_minimal.wasm')
    if (existsSync(src)) {
      copyFileSync(src, dest)
      console.log('[copy-rdkit-wasm] Copied RDKit_minimal.wasm → dist/')
    } else {
      console.warn('[copy-rdkit-wasm] WARNING: WASM source not found at', src)
    }
  },
})

export default defineConfig(({ mode }) => {
  return {
    plugins: [react(), copyRdkitWasm()],
    server: {
      host: '0.0.0.0',   // REQUIRED for Apptainer / Docker
      port: 32775,
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
        // Proxy the RDKit WASM file to Django in dev mode.
        // Without this, Vite intercepts /RDKit_minimal.wasm and returns
        // index.html, causing the "expected magic word" WebAssembly error.
        '/RDKit_minimal.wasm': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})