'use client'

import { useEffect, useRef } from 'react'

export interface TranscriptLine {
  timestamp: number
  text: string
  language: string
}

interface LiveTranscriptionProps {
  lines: TranscriptLine[]
}

export default function LiveTranscription({ lines }: LiveTranscriptionProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest line
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines.length])

  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-2 min-h-[140px]">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Live Transcription
        </h2>
        {lines.length > 0 && (
          <span className="text-xs text-gray-600">
            {lines.length} segment{lines.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {lines.length === 0 ? (
        <p className="text-xs text-gray-600 italic">
          Transcription will appear here as the video plays…
        </p>
      ) : (
        <div className="overflow-y-auto flex-1 max-h-36 flex flex-col gap-2 pr-1">
          {lines.map((line, i) => (
            <div key={i} className="flex gap-3 items-start">
              <span className="text-xs text-gray-600 tabular-nums shrink-0 pt-0.5">
                {formatTime(line.timestamp)}
              </span>
              <p className="text-sm text-gray-100 leading-relaxed">{line.text}</p>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
