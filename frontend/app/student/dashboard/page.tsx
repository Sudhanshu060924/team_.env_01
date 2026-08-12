'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { Lecture } from '@/types/lecture'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'
import LectureCard from '@/components/lecture/LectureCard'

type TabFilter = 'all' | 'completed' | 'live'

export default function StudentDashboard() {
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()
  const [lectures, setLectures] = useState<Lecture[]>([])
  const [lecturesLoading, setLecturesLoading] = useState(true)
  const [lecturesError, setLecturesError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<TabFilter>('all')

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login')
    }
    if (!isLoading && isAuthenticated && user?.role !== 'student') {
      router.replace('/teacher/dashboard')
    }
  }, [isLoading, isAuthenticated, user, router])

  useEffect(() => {
    if (!isAuthenticated) return
    api
      .listStudentLectures()
      .then(setLectures)
      .catch((err) => {
        setLecturesError(err instanceof Error ? err.message : 'Failed to load lectures')
      })
      .finally(() => setLecturesLoading(false))
  }, [isAuthenticated])

  if (!user) return null

  // Filtering
  const filtered = lectures.filter((l) => {
    const matchSearch =
      !search || l.title.toLowerCase().includes(search.toLowerCase())
    const matchTab =
      tab === 'all' ||
      (tab === 'completed' && l.status === 'completed') ||
      (tab === 'live' && l.status === 'live')
    return matchSearch && matchTab
  })

  const tabs: { id: TabFilter; label: string }[] = [
    { id: 'all', label: 'All Lectures' },
    { id: 'completed', label: 'Completed' },
    { id: 'live', label: 'In Progress' },
  ]

  return (
    <AppShell role="student">
      <AppHeader
        title={`Welcome back, ${user.name.split(' ')[0]} 👋`}
        subtitle="Continue learning from your lectures"
      />

      <PageContainer maxWidth="lg">
        {/* Section header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h2 className="text-xl font-bold text-black">My Lectures</h2>

          {/* Search + filter row */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search lectures…"
                className="pl-8 pr-3 py-2 text-sm border border-gray-300 rounded bg-white text-black placeholder-gray-400 focus:outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 w-52"
                aria-label="Search lectures"
              />
              <svg
                className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <circle cx="11" cy="11" r="8" />
                <path strokeLinecap="round" d="M21 21l-4.35-4.35" />
              </svg>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 border-b border-gray-200 mb-6" role="tablist">
          {tabs.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={[
                'px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
                tab === t.id
                  ? 'border-yellow-500 text-yellow-600 font-semibold'
                  : 'border-transparent text-gray-500 hover:text-gray-700',
              ].join(' ')}
            >
              {t.label}
              {t.id === 'all' && lectures.length > 0 && (
                <span className="ml-1.5 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                  {lectures.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        {lecturesLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-500 py-10 justify-center">
            <span className="w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
            Loading lectures…
          </div>
        )}

        {!lecturesLoading && lecturesError && (
          <p className="text-sm text-red-600 border border-red-200 bg-red-50 px-4 py-3 rounded">
            {lecturesError}
          </p>
        )}

        {!lecturesLoading && !lecturesError && filtered.length === 0 && (
          <div className="py-16 text-center">
            <p className="text-gray-500 text-sm">
              {search ? `No lectures matching "${search}"` : 'No lectures yet.'}
            </p>
          </div>
        )}

        {!lecturesLoading && !lecturesError && filtered.length > 0 && (
          <div className="flex flex-col gap-4">
            {filtered.map((lec) => (
              <LectureCard
                key={lec.lecture_id}
                lecture={lec}
                basePath="/student/lectures"
              />
            ))}
            <p className="text-xs text-gray-400 text-center pt-2">
              Showing {filtered.length} of {lectures.length} lecture{lectures.length !== 1 ? 's' : ''}
            </p>
          </div>
        )}
      </PageContainer>
    </AppShell>
  )
}
