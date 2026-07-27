// Import needed modules
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.js'

// Create root app and deploy it for the frontend
//
// Note: StrictMode intentionally double-invokes effects in development
// (not in production builds) to help surface side-effect bugs. That's
// relevant for effects elsewhere in this app that load external
// resources once (e.g. SkulptDisplay's Skulpt CDN script loading,
// MoleculeViewer's RDKit init) — those already guard against
// re-running (checking `window.Sk` / caching the init promise), which
// is exactly the kind of idempotency StrictMode is checking for.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
