'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { Lecture } from '@/types/lecture'
import { TeacherPerformanceScore } from '@/types/feedback'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import VideoUploadButton from '@/components/lecture/VideoUploadButton'

function StatCard({
  label,
  value,
  icon,
}: {
  label: string
  value: string | number
  icon: React.ReactNode
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg bg-yellow-50 border border-yellow-200 flex items-center justify-center text-yellow-600 shrink-0">
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-black leading-tight">{value}</p>
        <p className="text-xs text-gray-500 mt-0.5">{label}</p>
      </div>
    </div>
  )
}

function StarDisplay({ value }: { value: number }) {
  const full = Math.round(value)
  return (
    <span className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <svg key={s} width="13" height="13" viewBox="0 0 24 24"
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

export default function TeacherDashboard() {
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()
  const [lectures, setLectures] = useState<Lecture[]>([])
  const [lecturesLoading, setLecturesLoading] = useState(true)
  const [teacherScore, setTeacherScore] = useState<TeacherPerformanceScore | null>(null)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login')
    }
    if (!isLoading && isAuthenticated && user?.role !== 'teacher') {
      router.replace('/student/dashboard')
    }
  }, [isLoading, isAuthenticated, user, router])

  useEffect(() => {
    if (!isAuthenticated) return
    api
      .listTeacherLectures()
      .then(setLectures)
      .catch(() => {})
      .finally(() => setLecturesLoading(false))
    api.getTeacherScore().then(setTeacherScore).catch(() => {})
  }, [isAuthenticated])

  if (!user) return null

  const completed = lectures.filter((l) => l.status === 'completed').length
  const live = lectures.filter((l) => l.status === 'live').length

  return (
    <AppShell role="teacher">
      <AppHeader
        title={`Welcome back, ${user.name.split(' ')[0]} 👋`}
        subtitle="Manage your lectures and student learning"
      />

      <PageContainer maxWidth="lg">
        {/* Teacher performance score banner */}
        {teacherScore && teacherScore.overall != null && (
          <Link href="/teacher/feedback">
            <div className="bg-white border border-yellow-200 rounded-lg p-4 mb-6 flex items-center gap-4 hover:border-yellow-400 transition-colors cursor-pointer">
              <div className="w-10 h-10 rounded-lg bg-yellow-50 border border-yellow-200 flex items-center justify-center text-yellow-600 shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                </svg>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Teacher Performance Score</p>
                <div className="flex items-center gap-2">
                  <StarDisplay value={teacherScore.overall} />
                  <span className="text-xl font-bold text-black">{teacherScore.overall.toFixed(1)}</span>
                </div>
              </div>
              <div className="ml-auto text-xs text-gray-400 flex items-center gap-1">
                View details
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          </Link>
        )}

        {/* Overview stats */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
          <StatCard
            label="Total Lectures"
            value={lectures.length}
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.069A1 1 0 0121 8.862v6.276a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            }
          />
          <StatCard
            label="Completed"
            value={completed}
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            }
          />
          <StatCard
            label="Live Now"
            value={live}
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="3" /><path strokeLinecap="round" strokeLinejoin="round" d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14" />
              </svg>
            }
          />
        </div>

        {/* My Lectures */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-bold text-black">My Lectures</h2>
          <Link href="/teacher/upload">
            <Button variant="primary" size="sm">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Upload Video
            </Button>
          </Link>
        </div>

        {lecturesLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-500 py-10 justify-center">
            <span className="w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
            Loading lectures…
          </div>
        )}

        {!lecturesLoading && lectures.length === 0 && (
          <div className="border border-dashed border-gray-300 rounded-lg p-12 text-center">
            <p className="text-gray-600 font-medium mb-1">No lectures yet</p>
            <p className="text-sm text-gray-400 mb-4">Upload your first lecture video to get started.</p>
            <Link href="/teacher/upload">
              <Button variant="primary">Upload Video</Button>
            </Link>
          </div>
        )}

        {!lecturesLoading && lectures.length > 0 && (
          <div className="flex flex-col gap-4">
            {lectures.map((lec) => (
              <div key={lec.lecture_id} className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="font-semibold text-black text-sm">{lec.title}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{lec.video_name || '—'}</p>
                    <div className="flex items-center gap-2 mt-2">
                      {lec.status === 'completed' && <Badge variant="completed">Completed</Badge>}
                      {lec.status === 'live' && <Badge variant="live">● Live</Badge>}
                      {lec.status === 'available' && <Badge variant="completed">Available ✓</Badge>}
                      {lec.status !== 'completed' && lec.status !== 'live' && lec.status !== 'available' && (
                        <Badge variant="default">{lec.status}</Badge>
                      )}
                      {lec.video_url && (
                        <span className="text-xs text-green-600 font-medium">Video ✓</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {lec.created_at ? new Date(lec.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : ''}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <VideoUploadButton
                      lecture={lec}
                      onUploaded={(updated) =>
                        setLectures((prev) =>
                          prev.map((l) => (l.lecture_id === updated.lecture_id ? updated : l))
                        )
                      }
                    />
                    <Link href={`/teacher/lectures/${lec.lecture_id}/doubts`}>
                      <Button variant="secondary" size="sm">
                        Student Doubts
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </PageContainer>
    </AppShell>
  )
}
