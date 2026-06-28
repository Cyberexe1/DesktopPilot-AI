/**
 * WebSocket client — connects to the backend WS endpoint (derived from VITE_API_URL).
 * Used by the Vercel web dashboard to receive live execution updates.
 */

import { WS_URL } from './config'

let socket         = null
let reconnectTimer = null
let listeners      = {}

export function connectToAgent(onMessage, onStatusChange) {
  if (socket && socket.readyState === WebSocket.OPEN) return

  try {
    socket = new WebSocket(WS_URL)

    socket.onopen = () => {
      onStatusChange?.('connected')
      clearTimeout(reconnectTimer)
    }

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        onMessage?.(msg)
        listeners[msg.type]?.forEach(cb => cb(msg))
      } catch {}
    }

    socket.onclose = () => {
      onStatusChange?.('disconnected')
      socket = null
      reconnectTimer = setTimeout(() => connectToAgent(onMessage, onStatusChange), 4000)
    }

    socket.onerror = () => onStatusChange?.('error')

  } catch {
    onStatusChange?.('unavailable')
  }
}

export function disconnectFromAgent() {
  clearTimeout(reconnectTimer)
  socket?.close()
  socket = null
}

export function send(data) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(data))
    return true
  }
  return false
}

export function on(type, callback) {
  if (!listeners[type]) listeners[type] = []
  listeners[type].push(callback)
}

export function off(type, callback) {
  if (listeners[type]) {
    listeners[type] = listeners[type].filter(cb => cb !== callback)
  }
}

export function isConnected() {
  return socket?.readyState === WebSocket.OPEN
}
