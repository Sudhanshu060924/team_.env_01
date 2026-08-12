'use client'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'

export default function TeacherNotesPage() {
  return (
    <AppShell role="teacher">
      <AppHeader title="Notes" subtitle="All lecture notes from your sessions" />
      <PageContainer>
        <p className="text-sm text-gray-500 italic">Notes are available inside each lecture.</p>
      </PageContainer>
    </AppShell>
  )
}
