import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The app talks to the backend directly via VITE_API_URL (see src/lib/api.js),
// so no dev proxy is needed. Set VITE_API_URL in web/.env.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
})
