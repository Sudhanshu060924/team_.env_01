'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { LectureDoubtAnalytics, TopicAnalytic } from '@/types/chat'

interface DoubtAnalyticsPanelProps {
  lectureId: string
}

function ProgressBar({ percentage }: { percentage: number }) {
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
      <div
        className="h-2 rounded-full bg-yellow-400 transition-all duration-500"
        style={{ width: `${Math.min(percentage, 100)}%` }}
      />
    </div>
  )
}

function TopicRow({ topic, isActive, onClick }: {
  topic: TopicAnalytic
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'w-full text-left p-3 rounded-lg border transition-colors',
        isActive
          ? 'border-yellow-400 bg-yellow-50'
          : 'border-gray-200 hover:border-gray-300 bg-white',
      ].join(' ')}
    >
      <div className="flex items-center justify-between mb-1.5 gap-2">
        <span className="text-sm font-semibold text-black truncate">{topic.topic}</span>
        <span className="text-xs font-bold text-yellow-700 shrink-0">{topic.percentage}%</span>
      </div>
      <ProgressBar percentage={topic.percentage} />
      <p className="text-xs text-gray-500 mt-1.5">
        {topic.students_count} student{topic.students_count !== 1 ? 's' : ''} ·{' '}
        {topic.question_count} question{topic.question_count !== 1 ? 's' : ''}
      </p>
    </button>
  )
}

function TopicDetail({ topic }: { topic: TopicAnalytic }) {
  return (
    <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4 mt-3">
      <p className="text-xs uppercase tracking-widest text-yellow-700 font-semibold mb-2">
        Topic Detail
      </p>
      <p className="text-sm font-bold text-black mb-3">{topic.topic}</p>
      <div className="grid grid-cols-3 gap-3">
        <div className="text-center">
          <p className="text-xl font-bold text-black">{topic.students_count}</p>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">Students</p>
        </div>
        <div className="text-center">
          <p className="text-xl font-bold text-black">{topic.percentage}%</p>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">of students</p>
        </div>
        <div className="text-center">
          <p className="text-xl font-bold text-black">{topic.question_count}</p>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">Questions</p>
        </div>
      </div>
    </div>
  )
}

export default function DoubtAnalyticsPanel({ lectureId }: DoubtAnalyticsPanelProps) {
  const [analytics, setAnalytics] = useState<LectureDoubtAnalytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTopicName, setActiveTopicName] = useState<string | null>(null)

  useEffect(() => {
    if (!lectureId) return
    setLoading(true)
    api.getDoubtAnalytics(lectureId)
      .then((data) => {
        setAnalytics(data)
        setError(null)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load analytics')
      })
      .finally(() => setLoading(false))
  }, [lectureId])

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <p className="text-xs uppercase tracking-widest text-gray-500 font-semibold mb-4">
          Student Doubt Analytics
        </p>
        <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
          <span className="w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
          Loading analytics…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <p className="text-xs uppercase tracking-widest text-gray-500 font-semibold mb-2">
          Student Doubt Analytics
        </p>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    )
  }

  if (!analytics) return null

  const activeTopic = analytics.topics.find((t) => t.topic === activeTopicName) ?? null
  const noDoubts = analytics.students_with_doubts === 0

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      {/* Header */}
      <p className="text-xs uppercase tracking-widest text-gray-500 font-semibold mb-4">
        Student Doubt Analytics
      </p>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
          <p className="text-xl font-bold text-black">{analytics.students_with_doubts}</p>
          <p className="text-[10px] uppercase tracking-wider text-gray-500 mt-0.5">
            Students asked
          </p>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
          <p className="text-xl font-bold text-black">{analytics.total_questions}</p>
          <p className="text-[10px] uppercase tracking-wider text-gray-500 mt-0.5">
            Total questions
          </p>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
          <p className="text-sm font-bold text-black truncate" title={analytics.most_asked_topic ?? undefined}>
            {analytics.most_asked_topic ?? '—'}
          </p>
          <p className="text-[10px] uppercase tracking-wider text-gray-500 mt-0.5">
            Most asked
          </p>
        </div>
      </div>

      {noDoubts ? (
        <p className="text-sm text-gray-500 italic text-center py-4">
          No student doubts yet.
        </p>
      ) : (
        <>
          {/* Topic demand */}
          <p className="text-[10px] uppercase tracking-widest text-gray-500 font-semibold mb-2">
            Topic Demand
            <span className="ml-1.5 text-gray-400 normal-case font-normal tracking-normal">
              (% of students who asked about this topic)
            </span>
          </p>
          <div className="flex flex-col gap-2">
            {analytics.topics.map((topic) => (
              <TopicRow
                key={topic.topic}
                topic={topic}
                isActive={activeTopicName === topic.topic}
                onClick={() =>
                  setActiveTopicName((prev) => (prev === topic.topic ? null : topic.topic))
                }
              />
            ))}
          </div>
          {activeTopic && <TopicDetail topic={activeTopic} />}
        </>
      )}
    </div>
  )
}
