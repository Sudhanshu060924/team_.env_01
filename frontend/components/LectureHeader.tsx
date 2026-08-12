'use client'

import { WSStatus } from '@/hooks/useLectureWebSocket'
import { LectureStatus } from '@/types/lecture'
import ConnectionStatus from './ConnectionStatus'

interface LectureHeaderProps {
  title: string
  wsStatus: WSStatus
  lectureStatus: LectureStatus
}

export default function LectureHeader({ title, wsStatus, lectureStatus }: LectureHeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-3 bg-gray-900 border-b border-gray-800 shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-xl font-bold text-white tracking-tight">VidyaRoom</span>
        <span className="text-gray-400 text-sm truncate max-w-xs">{title}</span>
        {lectureStatus === 'live' && (
          <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded font-medium uppercase tracking-wide">
            Live
          </span>
        )}
        {lectureStatus === 'completed' && (
          <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded font-medium uppercase tracking-wide">
            Ended
          </span>
        )}
      </div>
      <ConnectionStatus status={wsStatus} />
    </header>
  )
}
