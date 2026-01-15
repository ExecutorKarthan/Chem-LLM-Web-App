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
    backendUrl = 'http://localhost:8000';
    console.log('Using DEVELOPMENT backend:', backendUrl);
  } else {
    backendUrl = '';  // Relative URLs in production
    console.log('Using PRODUCTION backend: (empty string = relative URLs)');
  }
  
  console.log('=================================');
  return backendUrl;
};

export const BACKEND_URL = getBackendUrl();