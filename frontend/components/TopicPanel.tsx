'use client'

import { TopicState } from '@/types/ai'

interface TopicPanelProps {
  topic: TopicState | null
}

export default function TopicPanel({ topic }: TopicPanelProps) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-2">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Current Topic</h2>
      {topic ? (
        <>
          <p className="text-base font-semibold text-white">{topic.topic}</p>
          {topic.subtopic && (
            <p className="text-sm text-indigo-300">{topic.subtopic}</p>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-600 italic">Topic will appear here…</p>
      )}
    </div>
  )
}
