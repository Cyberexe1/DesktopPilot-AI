/**
 * Centralized backend endpoints.
 * Set VITE_API_URL in web/.env (e.g. the App Runner URL).
 * WS_URL is derived from it (http->ws, https->wss) unless VITE_WS_URL is set.
 */

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8888').replace(/\/+$/, '')

export const WS_URL =
  import.meta.env.VITE_WS_URL ||
  API_URL.replace(/^http(s?):\/\//, (_, s) => (s ? 'wss://' : 'ws://')) + '/ws'
