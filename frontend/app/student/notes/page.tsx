'use client'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'

export default function StudentNotesPage() {
  return (
    <AppShell role="student">
      <AppHeader title="My Notes" subtitle="All your saved lecture notes" />
      <PageContainer>
        <p className="text-sm text-gray-500 italic">Notes will appear here once your lectures are processed.</p>
      </PageContainer>
    </AppShell>
  )
}
