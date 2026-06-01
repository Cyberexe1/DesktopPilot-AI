import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: BASE,
  timeout: 30000,
})

// ── Transcribe ────────────────────────────────────────────────────────────────
/**
 * Upload audio blob to backend → returns transcript string
 * @param {Blob} audioBlob
 * @returns {Promise<string>}
 */
export async function transcribeAudio(audioBlob) {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'recording.wav')

  const { data } = await client.post('/transcribe', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

  if (data.error) throw new Error(data.error)
  return data.data.text
}

// ── Plan ──────────────────────────────────────────────────────────────────────
/**
 * Send transcript to Bedrock planner → returns plan object
 * @param {string} text
 * @returns {Promise<{intent: string, tasks: Array, requires_approval: boolean}>}
 */
export async function generatePlan(text) {
  const { data } = await client.post('/plan', { text })
  if (data.error) throw new Error(data.error)
  return data.data.plan
}

// ── Execute ───────────────────────────────────────────────────────────────────
/**
 * Send plan to executor → streams step results via polling
 * @param {object} plan
 * @param {function} onStep  - called with (index, {success, message}) per step
 * @returns {Promise<Array>}
 */
export async function executePlan(plan, onStep) {
  const { data } = await client.post('/execute', { plan })
  if (data.error) throw new Error(data.error)

  const results = data.data.results
  results.forEach((result, index) => {
    if (onStep) onStep(index, result)
  })

  return results
}

// ── Health ────────────────────────────────────────────────────────────────────
export async function checkHealth() {
  try {
    const { data } = await client.get('/health')
    return data.status === 'ok'
  } catch {
    return false
  }
}

// ── Command history (DynamoDB via backend) ────────────────────────────────────
export async function getCommandHistory(userId = 'default') {
  const { data } = await client.get(`/memory/commands?user_id=${userId}`)
  if (data.error) throw new Error(data.error)
  return data.data.commands
}

export async function getMemory(userId = 'default') {
  const { data } = await client.get(`/memory?user_id=${userId}`)
  if (data.error) throw new Error(data.error)
  return data.data
}
