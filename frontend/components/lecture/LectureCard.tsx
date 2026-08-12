'use client'

import { Lecture } from '@/types/lecture'
import Badge from '@/components/ui/Badge'
import ProgressBar from '@/components/ui/ProgressBar'
import Button from '@/components/ui/Button'
import { useRouter } from 'next/navigation'

interface LectureCardProps {
  lecture: Lecture
  basePath: string  // e.g. '/student/lectures'
}

function formatDate(iso?: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function formatDuration(createdAt?: string, completedAt?: string | null): string {
  if (!createdAt || !completedAt) return '—'
  const diff = Math.floor(
    (new Date(completedAt).getTime() - new Date(createdAt).getTime()) / 1000
  )
  const m = Math.floor(diff / 60)
  const s = diff % 60
  if (m === 0) return `${s}s`
  return s === 0 ? `${m} min` : `${m}:${String(s).padStart(2, '0')}`
}

function LectureThumbnail({ title }: { title: string }) {
  // Generate a deterministic colour pair from title
  const colours = [
    ['#1e293b', '#f59e0b'],
    ['#1e3a5f', '#3b82f6'],
    ['#14532d', '#22c55e'],
    ['#4c1d95', '#a855f7'],
    ['#7f1d1d', '#ef4444'],
    ['#0c4a6e', '#0ea5e9'],
  ]
  const idx = Math.abs(title.charCodeAt(0) + title.charCodeAt(1 % title.length)) % colours.length
  const [bg, accent] = colours[idx]

  const words = title.toUpperCase().split(' ').slice(0, 3)
  return (
    <div
      className="w-full h-full flex flex-col items-center justify-center p-3 select-none"
      style={{ background: bg }}
    >
      {words.map((w, i) => (
        <span
          key={i}
          className="text-center font-bold leading-tight"
          style={{ color: i === words.length - 1 ? accent : '#ffffff', fontSize: '10px' }}
        >
          {w}
        </span>
      ))}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'completed')
    return (
      <Badge variant="completed">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        Completed
      </Badge>
    )
  if (status === 'live')
    return <Badge variant="live">● Live</Badge>
  return <Badge variant="notStarted">◷ Not Started</Badge>
}

export default function LectureCard({ lecture, basePath }: LectureCardProps) {
  const router = useRouter()
  const isCompleted = lecture.status === 'completed'
  const progress = isCompleted ? 100 : 0

  const ctaLabel = isCompleted ? 'Open Lecture' : lecture.status === 'live' ? 'Join Live' : 'Start Lecture'

  return (
    <div className="bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors flex gap-0 overflow-hidden">
      {/* Thumbnail */}
      <div className="w-[130px] sm:w-[160px] shrink-0 aspect-video sm:aspect-auto sm:h-auto">
        <div className="w-full h-full min-h-[90px]">
          <LectureThumbnail title={lecture.title} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col justify-between p-4 min-w-0 gap-2">
        {/* Top row */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-semibold text-black text-sm leading-snug truncate">{lecture.title}</h3>
            <p className="text-xs text-gray-500 mt-0.5 truncate">{lecture.video_name}</p>
          </div>
          <StatusBadge status={lecture.status} />
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 text-xs text-gray-500 flex-wrap">
          <span className="flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            {formatDate(lecture.created_at)}
          </span>
          <span className="flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
            </svg>
            {formatDuration(lecture.created_at, lecture.completed_at)}
          </span>
        </div>

        {/* Progress */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-gray-500">{progress}% Watched</span>
          </div>
          <ProgressBar value={progress} />
        </div>

        {/* CTA */}
        <div className="flex items-center justify-end">
          <Button
            variant="primary"
            size="sm"
            onClick={() => router.push(`${basePath}/${lecture.lecture_id}`)}
          >
            {ctaLabel}
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </Button>
        </div>
      </div>
    </div>
  )
}
