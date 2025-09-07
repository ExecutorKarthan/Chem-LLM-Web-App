// Import needed modules
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.js'

// Create root app and deploy it for the frontend
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
