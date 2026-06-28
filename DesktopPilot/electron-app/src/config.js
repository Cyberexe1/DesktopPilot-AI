/**
 * API endpoints for the desktop renderer.
 *
 * LOCAL_API  — the bundled FastAPI agent (desktop control, files, TTS, etc.).
 * CLOUD_API  — the hosted App Runner backend that holds AWS credentials.
 *
 * AWS-dependent calls (/plan, /transcribe) go to CLOUD_API so no AWS keys
 * ever ship inside the installer. Everything else stays local.
 */

export const LOCAL_API = 'http://localhost:8888'

export const CLOUD_API =
  (import.meta.env.VITE_CLOUD_API_URL || 'https://8dv6pa7ee8.us-east-1.awsapprunner.com').replace(/\/+$/, '')
