'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'
import LectureCard from '@/components/lecture/LectureCard'
import { api } from '@/lib/api'
import { Lecture } from '@/types/lecture'
import { useState } from 'react'

export default function StudentLecturesPage() {
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()
  const [lectures, setLectures] = useState<Lecture[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace('/login')
  }, [isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!isAuthenticated) return
    api.listStudentLectures()
      .then(setLectures)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [isAuthenticated])

  if (!user) return null

  return (
    <AppShell role="student">
      <AppHeader title="My Lectures" subtitle="All your lectures" />
      <PageContainer>
        {loading && <p className="text-sm text-gray-500">Loading…</p>}
        {!loading && lectures.length === 0 && (
          <p className="text-sm text-gray-500 italic">No lectures yet.</p>
        )}
        {!loading && lectures.length > 0 && (
          <div className="flex flex-col gap-4">
            {lectures.map((l) => (
              <LectureCard key={l.lecture_id} lecture={l} basePath="/student/lectures" />
            ))}
          </div>
        )}
      </PageContainer>
    </AppShell>
  )
}
