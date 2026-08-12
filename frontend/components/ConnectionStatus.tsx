'use client'

import { WSStatus } from '@/hooks/useLectureWebSocket'

interface ConnectionStatusProps {
  status: WSStatus | 'processing'
}

const CONFIG: Record<string, { dot: string; label: string; text: string }> = {
  connected:    { dot: 'bg-green-400',  label: 'Connected',    text: 'text-green-400' },
  connecting:   { dot: 'bg-yellow-400 animate-pulse', label: 'Connecting…', text: 'text-yellow-400' },
  processing:   { dot: 'bg-blue-400 animate-pulse',   label: 'Processing',  text: 'text-blue-400' },
  disconnected: { dot: 'bg-gray-500',   label: 'Disconnected', text: 'text-gray-400' },
  error:        { dot: 'bg-red-400',    label: 'Error',        text: 'text-red-400' },
}

export default function ConnectionStatus({ status }: ConnectionStatusProps) {
  const c = CONFIG[status] ?? CONFIG.disconnected
  return (
    <div className={`flex items-center gap-2 text-sm font-medium ${c.text}`}>
      <span className={`inline-block w-2 h-2 rounded-full ${c.dot}`} />
      {c.label}
    </div>
  )
}
