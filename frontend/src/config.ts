// src/config.ts
const isDevelopment = import.meta.env.DEV;

export const BACKEND_URL = isDevelopment 
  ? (import.meta.env.VITE_BACKEND_URL_DEV || '')
  : 'http://llmexplorer.engr.wustl.edu:8000';