// src/config.ts
const isDevelopment = import.meta.env.DEV;

const getBackendUrl = () => {
  console.log('=== BACKEND URL CONFIGURATION ===');
  console.log('Environment:', isDevelopment ? 'DEVELOPMENT' : 'PRODUCTION');
  console.log('import.meta.env.DEV:', import.meta.env.DEV);
  console.log('import.meta.env.MODE:', import.meta.env.MODE);
  console.log('window.location.hostname:', window.location.hostname);
  console.log('window.location.href:', window.location.href);
  
  let backendUrl: string;
  
  if (isDevelopment) {
    // Development mode: Vite dev server on port 32780
    // Proxy will forward /api requests to localhost:8000
    backendUrl = 'http://localhost:8000';
    console.log('Using DEVELOPMENT backend:', backendUrl);
  } else {
    // Production mode: Django serves everything
    // Use relative URLs - works for both localhost and production server
    backendUrl = '';
    console.log('Using PRODUCTION backend: (empty string = relative URLs)');
    console.log('API calls will use relative paths like: /api/check-cookie/');
    console.log('Browser will resolve to:', window.location.origin + '/api/...');
  }
  
  console.log('=================================');
  return backendUrl;
};

export const BACKEND_URL = getBackendUrl();