'use client'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'

export default function TeacherDoubtsPage() {
  return (
    <AppShell role="teacher">
      <AppHeader title="Student Doubts" subtitle="All doubts across your lectures" />
      <PageContainer>
        <p className="text-sm text-gray-500 italic">
          Open a specific lecture from My Lectures to view and reply to student doubts.
        </p>
      </PageContainer>
    </AppShell>
  )
}
