'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { Lecture } from '@/types/lecture'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Link from 'next/link'
import VideoUploadButton from '@/components/lecture/VideoUploadButton'

export default function TeacherLecturesPage() {
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()
  const [lectures, setLectures] = useState<Lecture[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace('/login')
    if (!isLoading && isAuthenticated && user?.role !== 'teacher') router.replace('/student/dashboard')
  }, [isLoading, isAuthenticated, user, router])

  useEffect(() => {
    if (!isAuthenticated) return
    api.listTeacherLectures()
      .then(setLectures)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [isAuthenticated])

  if (!user) return null

  return (
    <AppShell role="teacher">
      <AppHeader title="My Lectures" subtitle="All your lectures" />
      <PageContainer>
        {loading && <p className="text-sm text-gray-500">Loading…</p>}
        {!loading && lectures.length === 0 && (
          <div className="border border-dashed border-gray-300 rounded-lg p-12 text-center">
            <p className="text-gray-600 font-medium mb-1">No lectures yet</p>
            <Link href="/"><Button variant="primary">Start Lecture</Button></Link>
          </div>
        )}
        {!loading && lectures.length > 0 && (
          <div className="flex flex-col gap-3">
            {lectures.map((lec) => (
              <div key={lec.lecture_id} className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between gap-4 hover:border-gray-300 transition-colors">
                <div>
                  <p className="font-semibold text-black text-sm">{lec.title}</p>
                  <div className="flex gap-2 mt-1">
                    {lec.status === 'completed' && <Badge variant="completed">Completed</Badge>}
                    {lec.status === 'live' && <Badge variant="live">● Live</Badge>}
                    {lec.status !== 'completed' && lec.status !== 'live' && <Badge>{lec.status}</Badge>}
                  </div>
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
                    <Button variant="secondary" size="sm">View Doubts</Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </PageContainer>
    </AppShell>
  )
}
