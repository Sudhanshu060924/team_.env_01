'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { WSMessage } from '@/types/ai'

export type WSStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

interface UseLectureWebSocketOptions {
  lectureId: string | null
  onMessage: (msg: WSMessage) => void
}

export function useLectureWebSocket({ lectureId, onMessage }: UseLectureWebSocketOptions) {
  const [status, setStatus] = useState<WSStatus>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    if (wsRef.current) {
      wsRef.current.onclose = null // prevent reconnect loop
      wsRef.current.close()
      wsRef.current = null
    }
    if (mountedRef.current) setStatus('disconnected')
  }, [])

  const connect = useCallback(() => {
    if (!lectureId) return
    disconnect()

    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'
    const url = `${wsBase}/ws/lectures/${lectureId}`
    setStatus('connecting')

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (mountedRef.current) setStatus('connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        onMessageRef.current(msg)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => {
      if (mountedRef.current) setStatus('error')
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setStatus('disconnected')
      // Auto-reconnect after 3 s
      reconnectTimer.current = setTimeout(() => {
        if (mountedRef.current && lectureId) connect()
      }, 3000)
    }
  }, [lectureId, disconnect])

  // Connect when lectureId becomes available
  useEffect(() => {
    if (lectureId) {
      connect()
    } else {
      disconnect()
    }
    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [lectureId]) // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  // Keepalive ping every 20 s
  useEffect(() => {
    if (status !== 'connected') return
    const id = setInterval(() => sendMessage({ type: 'ping' }), 20_000)
    return () => clearInterval(id)
  }, [status, sendMessage])

  return { status, sendMessage, disconnect, connect }
}
