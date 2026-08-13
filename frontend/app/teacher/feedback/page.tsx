'use client'

import { useEffect, useState, useCallback, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { Lecture } from '@/types/lecture'
import { FeedbackOverview, FeedbackTopic, RatingAnalytics, WrittenReview } from '@/types/feedback'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatRating(v: number | null | undefined): string {
  if (v == null) return '—'
  return v.toFixed(1)
}

function StarDisplay({ value }: { value: number }) {
  const full = Math.round(value)
  return (
    <span className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <svg key={s} width="14" height="14" viewBox="0 0 24 24"
          fill={s <= full ? '#f59e0b' : 'none'}
          stroke={s <= full ? '#f59e0b' : '#d1d5db'}
          strokeWidth={1.8}
        >
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      ))}
    </span>
  )
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, icon, accent }: {
  label: string
  value: string | number | ReactNode
  icon: ReactNode
  accent?: boolean
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 flex items-center gap-4">
      <div className={[
        'w-10 h-10 rounded-lg border flex items-center justify-center shrink-0',
        accent ? 'bg-yellow-50 border-yellow-200 text-yellow-600' : 'bg-gray-50 border-gray-200 text-gray-500',
      ].join(' ')}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold text-black leading-tight">{value}</div>
        <p className="text-xs text-gray-500 mt-0.5">{label}</p>
      </div>
    </div>
  )
}

// ── Section heading ───────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <p className="text-xs uppercase tracking-widest text-gray-500 font-semibold mb-3">
      {children}
    </p>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 py-8 justify-center">
      <span className="w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
      Loading…
    </div>
  )
}

// ── Topic Bar Chart ───────────────────────────────────────────────────────────

function TopicBarChart({ topics, activeTopicName, onTopicClick }: {
  topics: FeedbackTopic[]
  activeTopicName: string | null
  // eslint-disable-next-line no-unused-vars
  onTopicClick: (topicName: string) => void
}) {
  const [hoveredTopic, setHoveredTopic] = useState<string | null>(null)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; topic: FeedbackTopic } | null>(null)

  if (topics.length === 0) return null

  const displayTopics = topics.slice(0, 8)
  const maxPct = Math.max(...displayTopics.map((t) => t.percentage))

  const BAR_HEIGHT = 36, BAR_GAP = 10, LABEL_WIDTH = 160, PCT_WIDTH = 50, BAR_AREA = 300
  const SVG_WIDTH = LABEL_WIDTH + BAR_AREA + PCT_WIDTH + 20
  const SVG_HEIGHT = displayTopics.length * (BAR_HEIGHT + BAR_GAP) + 8
  const COLORS = ['#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ef4444', '#f97316', '#06b6d4', '#84cc16']

  return (
    <div className="relative overflow-x-auto">
      <svg width={SVG_WIDTH} viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`} className="w-full" style={{ fontFamily: 'inherit' }}>
        {displayTopics.map((t, i) => {
          const y = i * (BAR_HEIGHT + BAR_GAP) + 4
          const barW = maxPct > 0 ? (t.percentage / maxPct) * BAR_AREA : 0
          const isActive = activeTopicName === t.topic
          const isHovered = hoveredTopic === t.topic
          const color = COLORS[i % COLORS.length]
          return (
            <g key={t.topic} style={{ cursor: 'pointer' }}
              onClick={() => onTopicClick(t.topic)}
              onMouseEnter={(e) => {
                setHoveredTopic(t.topic)
                const rect = (e.currentTarget as SVGGElement).closest('svg')?.getBoundingClientRect()
                if (rect) setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, topic: t })
              }}
              onMouseMove={(e) => {
                const rect = (e.currentTarget as SVGGElement).closest('svg')?.getBoundingClientRect()
                if (rect) setTooltip((prev) => prev ? { ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top } : prev)
              }}
              onMouseLeave={() => { setHoveredTopic(null); setTooltip(null) }}
            >
              <rect x={0} y={y} width={SVG_WIDTH} height={BAR_HEIGHT} fill="transparent" />
              <text x={LABEL_WIDTH - 10} y={y + BAR_HEIGHT / 2 + 4} textAnchor="end" fontSize={12}
                fill={isActive ? '#92400e' : '#374151'} fontWeight={isActive ? '600' : '400'}>
                {t.topic.length > 18 ? t.topic.slice(0, 17) + '…' : t.topic}
              </text>
              <rect x={LABEL_WIDTH} y={y + 10} width={BAR_AREA} height={BAR_HEIGHT - 20} fill="#f3f4f6" rx={4} />
              <rect x={LABEL_WIDTH} y={y + 10} width={Math.max(barW, 0)} height={BAR_HEIGHT - 20}
                fill={isActive || isHovered ? color : color + 'cc'} rx={4} style={{ transition: 'width 0.4s ease' }} />
              {(isActive || isHovered) && (
                <rect x={LABEL_WIDTH} y={y + 10} width={BAR_AREA} height={BAR_HEIGHT - 20} fill="none" stroke={color} strokeWidth={1.5} rx={4} />
              )}
              <text x={LABEL_WIDTH + BAR_AREA + 8} y={y + BAR_HEIGHT / 2 + 4} fontSize={12} fill="#6b7280" fontWeight="600">
                {t.percentage}%
              </text>
            </g>
          )
        })}
      </svg>
      {tooltip && (
        <div className="pointer-events-none absolute z-20 bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs"
          style={{ left: Math.min(tooltip.x + 12, SVG_WIDTH - 140), top: Math.max(tooltip.y - 60, 0), minWidth: 130 }}>
          <p className="font-semibold text-black mb-1">{tooltip.topic.topic}</p>
          <p className="text-gray-600">{tooltip.topic.question_count} question{tooltip.topic.question_count !== 1 ? 's' : ''}</p>
          <p className="text-yellow-700 font-semibold">{tooltip.topic.percentage}%</p>
          {tooltip.topic.lecture_title && <p className="text-gray-400 mt-0.5 truncate">{tooltip.topic.lecture_title}</p>}
        </div>
      )}
    </div>
  )
}

// ── Topic Table ───────────────────────────────────────────────────────────────

function TopicTable({ topics, activeTopic, onRowClick }: {
  topics: FeedbackTopic[]
  activeTopic: FeedbackTopic | null
  // eslint-disable-next-line no-unused-vars
  onRowClick: (topic: FeedbackTopic) => void
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-3 px-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Topic</th>
            <th className="text-right py-3 px-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Questions</th>
            <th className="text-right py-3 px-3 text-xs uppercase tracking-wider text-gray-500 font-semibold">Share</th>
            {topics.some((t) => t.lecture_title) && (
              <th className="text-left py-3 px-3 text-xs uppercase tracking-wider text-gray-500 font-semibold hidden sm:table-cell">Lecture</th>
            )}
          </tr>
        </thead>
        <tbody>
          {topics.map((t, i) => {
            const isActive = activeTopic?.topic === t.topic && activeTopic?.lecture_id === t.lecture_id
            const isTop = i === 0
            return (
              <tr key={`${t.topic}-${t.lecture_id ?? 'all'}`} onClick={() => onRowClick(t)}
                className={['border-b border-gray-100 cursor-pointer transition-colors',
                  isActive ? 'bg-yellow-50 border-yellow-200' : 'hover:bg-gray-50'].join(' ')}>
                <td className="py-2.5 px-3">
                  <div className="flex items-center gap-2">
                    {isTop && <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-yellow-100 text-yellow-700 shrink-0">#1</span>}
                    <span className={['font-medium', isTop ? 'text-black' : 'text-gray-700'].join(' ')}>{t.topic}</span>
                  </div>
                </td>
                <td className="py-2.5 px-3 text-right font-semibold text-black">{t.question_count}</td>
                <td className="py-2.5 px-3 text-right">
                  <span className={['font-semibold', isTop ? 'text-yellow-700' : 'text-gray-600'].join(' ')}>{t.percentage}%</span>
                </td>
                {topics.some((x) => x.lecture_title) && (
                  <td className="py-2.5 px-3 text-gray-500 text-xs hidden sm:table-cell truncate max-w-[180px]">{t.lecture_title ?? '—'}</td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Rating Distribution Chart ─────────────────────────────────────────────────

function RatingDistributionChart({ analytics }: { analytics: RatingAnalytics }) {
  const [hovered, setHovered] = useState<number | null>(null)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; star: number } | null>(null)

  if (analytics.total_ratings === 0) {
    return <p className="text-sm text-gray-400 italic py-4 text-center">No ratings yet.</p>
  }

  const dist = analytics.distribution
  const bars: { star: number; count: number }[] = [
    { star: 5, count: dist.five },
    { star: 4, count: dist.four },
    { star: 3, count: dist.three },
    { star: 2, count: dist.two },
    { star: 1, count: dist.one },
  ]
  const maxCount = Math.max(...bars.map((b) => b.count), 1)

  const BAR_HEIGHT = 32, BAR_GAP = 8, LABEL_WIDTH = 60, COUNT_WIDTH = 50, BAR_AREA = 260
  const SVG_WIDTH = LABEL_WIDTH + BAR_AREA + COUNT_WIDTH + 10
  const SVG_HEIGHT = bars.length * (BAR_HEIGHT + BAR_GAP) + 4

  return (
    <div className="relative overflow-x-auto">
      <svg width={SVG_WIDTH} viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`} className="w-full" style={{ fontFamily: 'inherit' }}>
        {bars.map(({ star, count }, i) => {
          const y = i * (BAR_HEIGHT + BAR_GAP) + 2
          const barW = maxCount > 0 ? (count / maxCount) * BAR_AREA : 0
          const pct = analytics.total_ratings > 0 ? Math.round(count / analytics.total_ratings * 100) : 0
          const isHov = hovered === star

          return (
            <g key={star} style={{ cursor: 'pointer' }}
              onMouseEnter={(e) => {
                setHovered(star)
                const rect = (e.currentTarget as SVGGElement).closest('svg')?.getBoundingClientRect()
                if (rect) setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, star })
              }}
              onMouseMove={(e) => {
                const rect = (e.currentTarget as SVGGElement).closest('svg')?.getBoundingClientRect()
                if (rect) setTooltip((prev) => prev ? { ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top } : prev)
              }}
              onMouseLeave={() => { setHovered(null); setTooltip(null) }}
            >
              <rect x={0} y={y} width={SVG_WIDTH} height={BAR_HEIGHT} fill="transparent" />
              {/* Star label */}
              <text x={LABEL_WIDTH - 6} y={y + BAR_HEIGHT / 2 + 4} textAnchor="end" fontSize={12} fill={isHov ? '#92400e' : '#374151'} fontWeight={isHov ? '600' : '400'}>
                {'★'.repeat(star)}
              </text>
              {/* Track */}
              <rect x={LABEL_WIDTH} y={y + 8} width={BAR_AREA} height={BAR_HEIGHT - 16} fill="#f3f4f6" rx={4} />
              {/* Fill */}
              <rect x={LABEL_WIDTH} y={y + 8} width={Math.max(barW, 0)} height={BAR_HEIGHT - 16}
                fill={isHov ? '#f59e0b' : '#fbbf24'} rx={4} style={{ transition: 'width 0.4s ease' }} />
              {/* Percent label */}
              <text x={LABEL_WIDTH + BAR_AREA + 6} y={y + BAR_HEIGHT / 2 + 4} fontSize={11} fill="#6b7280" fontWeight="600">
                {pct}%
              </text>
            </g>
          )
        })}
      </svg>

      {tooltip && (() => {
        const b = bars.find((x) => x.star === tooltip.star)
        if (!b) return null
        const pct = analytics.total_ratings > 0 ? Math.round(b.count / analytics.total_ratings * 100) : 0
        return (
          <div className="pointer-events-none absolute z-20 bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs"
            style={{ left: Math.min(tooltip.x + 12, SVG_WIDTH - 130), top: Math.max(tooltip.y - 60, 0), minWidth: 110 }}>
            <p className="font-semibold text-black mb-1">{'★'.repeat(b.star)} {b.star} star{b.star !== 1 ? 's' : ''}</p>
            <p className="text-gray-600">{b.count} rating{b.count !== 1 ? 's' : ''}</p>
            <p className="text-yellow-700 font-semibold">{pct}%</p>
          </div>
        )
      })()}
    </div>
  )
}

// ── Written Reviews List ──────────────────────────────────────────────────────

function ReviewsList({ reviews }: { reviews: WrittenReview[] }) {
  if (reviews.length === 0) {
    return <p className="text-sm text-gray-400 italic py-4 text-center">No written feedback yet.</p>
  }
  return (
    <div className="flex flex-col gap-3">
      {reviews.map((r, i) => (
        <div key={i} className="border border-gray-200 rounded-lg p-4 bg-white">
          <div className="flex items-center gap-2 mb-2">
            {[1,2,3,4,5].map((s) => (
              <svg key={s} width="13" height="13" viewBox="0 0 24 24"
                fill={s <= r.rating ? '#f59e0b' : 'none'}
                stroke={s <= r.rating ? '#f59e0b' : '#d1d5db'}
                strokeWidth={1.8}>
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
            ))}
          </div>
          <p className="text-sm text-gray-800 italic mb-2">&ldquo;{r.feedback}&rdquo;</p>
          <p className="text-[11px] text-gray-400">
            {new Date(r.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
          </p>
        </div>
      ))}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TeacherFeedbackPage() {
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()

  const [lectures, setLectures] = useState<Lecture[]>([])
  const [selectedLectureId, setSelectedLectureId] = useState<string>('')

  const [overview, setOverview] = useState<FeedbackOverview | null>(null)
  const [topics, setTopics] = useState<FeedbackTopic[]>([])
  const [ratingAnalytics, setRatingAnalytics] = useState<RatingAnalytics | null>(null)
  const [reviews, setReviews] = useState<WrittenReview[]>([])

  const [overviewLoading, setOverviewLoading] = useState(true)
  const [topicsLoading, setTopicsLoading] = useState(true)
  const [ratingsLoading, setRatingsLoading] = useState(false)
  const [reviewsLoading, setReviewsLoading] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [activeTopic, setActiveTopic] = useState<FeedbackTopic | null>(null)

  // Auth guard
  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace('/login')
    if (!isLoading && isAuthenticated && user?.role !== 'teacher') router.replace('/student/dashboard')
  }, [isLoading, isAuthenticated, user, router])

  // Load lectures for filter
  useEffect(() => {
    if (!isAuthenticated) return
    api.listTeacherLectures().then(setLectures).catch(() => {})
  }, [isAuthenticated])

  const lectureIdArg = selectedLectureId || undefined

  const loadData = useCallback(() => {
    if (!isAuthenticated) return
    setOverviewLoading(true)
    setTopicsLoading(true)
    setActiveTopic(null)
    setError(null)
    setRatingAnalytics(null)
    setReviews([])

    api.getFeedbackOverview(lectureIdArg)
      .then(setOverview)
      .catch((e: Error) => setError(e.message))
      .finally(() => setOverviewLoading(false))

    api.getFeedbackTopics(lectureIdArg)
      .then(setTopics)
      .catch(() => {})
      .finally(() => setTopicsLoading(false))

    // Rating analytics + reviews only available when a specific lecture is selected
    if (lectureIdArg) {
      setRatingsLoading(true)
      setReviewsLoading(true)
      api.getLectureRatingAnalytics(lectureIdArg)
        .then(setRatingAnalytics)
        .catch(() => setRatingAnalytics({ avg_rating: null, total_ratings: 0, distribution: { five: 0, four: 0, three: 0, two: 0, one: 0 } }))
        .finally(() => setRatingsLoading(false))
      api.getLectureWrittenReviews(lectureIdArg)
        .then(setReviews)
        .catch(() => setReviews([]))
        .finally(() => setReviewsLoading(false))
    }
  }, [isAuthenticated, lectureIdArg])

  useEffect(() => { loadData() }, [loadData])

  if (!user) return null

  const handleTopicToggle = (topicName: string) => {
    const matched = topics.find((t) => t.topic === topicName) ?? null
    setActiveTopic((prev) => prev?.topic === topicName && prev?.lecture_id === matched?.lecture_id ? null : matched)
  }
  const handleTableRowClick = (t: FeedbackTopic) => {
    setActiveTopic((prev) => prev?.topic === t.topic && prev?.lecture_id === t.lecture_id ? null : t)
  }

  const hasTopics = !overviewLoading && !topicsLoading && topics.length > 0
  const hasNoData = !overviewLoading && !topicsLoading && topics.length === 0
    && (overview?.total_ratings ?? 0) === 0 && !error
  const showRatings = !!lectureIdArg

  // Icons
  const iconLectures = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.069A1 1 0 0121 8.862v6.276a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
  const iconStudents = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-4A4 4 0 1112 4a4 4 0 010 8z" /></svg>
  const iconQuestion = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
  const iconDoubts = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" /></svg>
  const iconAI = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
  const iconTopic = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
  const iconStar = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" /></svg>
  const iconRatings = <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>

  return (
    <AppShell role="teacher">
      <AppHeader title="Feedback" subtitle="Student engagement & lecture quality analytics" />
      <PageContainer maxWidth="lg">

        {/* ── Lecture filter ── */}
        <div className="flex items-center gap-3 mb-6">
          <label className="text-xs uppercase tracking-wider text-gray-500 font-semibold shrink-0">Lecture</label>
          <select
            value={selectedLectureId}
            onChange={(e) => setSelectedLectureId(e.target.value)}
            className="bg-white border border-gray-200 rounded-md text-sm text-gray-700 px-3 py-1.5 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 transition-colors"
          >
            <option value="">All Lectures</option>
            {lectures.map((l) => (
              <option key={l.lecture_id} value={l.lecture_id}>{l.title}</option>
            ))}
          </select>
        </div>

        {error && (
          <div className="border border-red-200 bg-red-50 rounded-lg px-4 py-3 text-sm text-red-600 mb-6">{error}</div>
        )}

        {/* ── Overview stat cards ── */}
        {overviewLoading ? <Spinner /> : overview ? (
          <>
            {/* Section A: Lecture Engagement */}
            <div className="mb-2">
              <SectionHeading>Lecture Engagement</SectionHeading>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
              <StatCard label="Total Lectures" value={overview.total_lectures} accent icon={iconLectures} />
              <StatCard label="Total Students" value={overview.total_students} icon={iconStudents} />
              <StatCard label="Total Questions" value={overview.total_questions} icon={iconQuestion} />
              <StatCard label="Teacher-Student Doubts" value={overview.total_doubts} icon={iconDoubts} />
              <StatCard label="AI Chatbot Questions" value={overview.total_ai_questions} icon={iconAI} />
              <StatCard label="Most Asked Topic" value={overview.most_asked_topic ?? '—'} accent={!!overview.most_asked_topic} icon={iconTopic} />
            </div>

            {/* Section B: Lecture Quality */}
            <div className="mb-2">
              <SectionHeading>Lecture Quality</SectionHeading>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
              <StatCard
                label="Average Rating"
                accent={overview.avg_rating != null}
                icon={iconStar}
                value={
                  overview.avg_rating != null ? (
                    <span className="flex items-center gap-1.5">
                      <StarDisplay value={overview.avg_rating} />
                      <span className="text-xl font-bold">{formatRating(overview.avg_rating)}</span>
                    </span>
                  ) : '—'
                }
              />
              <StatCard label="Total Ratings" value={overview.total_ratings} icon={iconRatings} />
              <StatCard
                label="Most Rated Lecture"
                value={overview.most_rated_lecture ?? '—'}
                accent={!!overview.most_rated_lecture}
                icon={iconStar}
              />
            </div>
          </>
        ) : null}

        {/* ── Empty state ── */}
        {hasNoData && (
          <div className="border border-dashed border-gray-300 rounded-lg p-12 text-center mb-6">
            <div className="flex justify-center mb-3 text-gray-300">
              <svg className="w-12 h-12" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <p className="text-gray-600 font-medium mb-1">No student feedback yet.</p>
            <p className="text-sm text-gray-400">Analytics will appear once students start asking questions or leaving ratings.</p>
          </div>
        )}

        {/* ── Topic analytics ── */}
        {hasTopics && (
          <>
            <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6">
              <div className="flex items-center justify-between mb-4">
                <SectionHeading>Topic Distribution</SectionHeading>
                <p className="text-xs text-gray-400">Click a bar to see details</p>
              </div>
              <TopicBarChart topics={topics} activeTopicName={activeTopic?.topic ?? null} onTopicClick={handleTopicToggle} />
              {activeTopic && (
                <div className="mt-4 border border-yellow-200 bg-yellow-50 rounded-lg p-4">
                  <p className="text-xs uppercase tracking-widest text-yellow-700 font-semibold mb-2">Topic Detail</p>
                  <p className="text-sm font-bold text-black mb-3">{activeTopic.topic}</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="text-center">
                      <p className="text-xl font-bold text-black">{activeTopic.question_count}</p>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">AI Questions</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xl font-bold text-black">{activeTopic.percentage}%</p>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">of questions</p>
                    </div>
                    {activeTopic.lecture_title && (
                      <div className="text-center">
                        <p className="text-sm font-bold text-black truncate" title={activeTopic.lecture_title}>{activeTopic.lecture_title}</p>
                        <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">Lecture</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden mb-8">
              <div className="px-5 py-4 border-b border-gray-100">
                <SectionHeading>
                  Topic Breakdown
                  <span className="ml-1.5 text-gray-400 normal-case font-normal tracking-normal">— sorted by most asked</span>
                </SectionHeading>
              </div>
              {topicsLoading ? <div className="p-5"><Spinner /></div> : (
                <TopicTable topics={topics} activeTopic={activeTopic} onRowClick={handleTableRowClick} />
              )}
            </div>
          </>
        )}

        {/* ── Rating analytics (per-lecture only) ── */}
        {showRatings && (
          <>
            <div className="mb-2">
              <SectionHeading>
                Lecture Rating
                {lectures.find((l) => l.lecture_id === selectedLectureId)?.title && (
                  <span className="ml-2 normal-case font-normal text-gray-400 tracking-normal">
                    — {lectures.find((l) => l.lecture_id === selectedLectureId)?.title}
                  </span>
                )}
              </SectionHeading>
            </div>

            {ratingsLoading ? <Spinner /> : ratingAnalytics ? (
              <>
                {/* Rating summary */}
                <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-5">
                    <div className="text-center sm:text-left">
                      <p className="text-4xl font-bold text-black">{formatRating(ratingAnalytics.avg_rating)}</p>
                      <div className="flex justify-center sm:justify-start mt-1">
                        {ratingAnalytics.avg_rating != null
                          ? <StarDisplay value={ratingAnalytics.avg_rating} />
                          : <p className="text-xs text-gray-400">No ratings yet</p>
                        }
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{ratingAnalytics.total_ratings} rating{ratingAnalytics.total_ratings !== 1 ? 's' : ''}</p>
                    </div>
                    <div className="flex-1">
                      {/* Per-star summary rows */}
                      {([5,4,3,2,1] as const).map((star) => {
                        const key = (['five','four','three','two','one'] as const)[5 - star]
                        const count = ratingAnalytics.distribution[key]
                        const pct = ratingAnalytics.total_ratings > 0 ? Math.round(count / ratingAnalytics.total_ratings * 100) : 0
                        return (
                          <div key={star} className="flex items-center gap-2 mb-1">
                            <span className="text-xs text-yellow-500 shrink-0 w-16">{star} {'★'.repeat(star)}</span>
                            <div className="flex-1 bg-gray-100 rounded-full h-2">
                              <div className="h-2 rounded-full bg-yellow-400 transition-all duration-500" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="text-xs text-gray-500 w-8 text-right shrink-0">{pct}%</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  <SectionHeading>Rating Distribution</SectionHeading>
                  <RatingDistributionChart analytics={ratingAnalytics} />
                </div>
              </>
            ) : null}

            {/* Written feedback */}
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden mb-8">
              <div className="px-5 py-4 border-b border-gray-100">
                <SectionHeading>Student Feedback</SectionHeading>
              </div>
              <div className="p-5">
                {reviewsLoading ? <Spinner /> : <ReviewsList reviews={reviews} />}
              </div>
            </div>
          </>
        )}

        {/* Hint when no lecture is selected */}
        {!showRatings && !hasNoData && (
          <div className="border border-dashed border-gray-200 rounded-lg p-6 text-center text-sm text-gray-400">
            Select a specific lecture above to see its rating distribution and written student feedback.
          </div>
        )}

      </PageContainer>
    </AppShell>
  )
}
