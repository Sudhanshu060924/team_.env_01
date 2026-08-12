'use client'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'

export default function StudentDoubtsPage() {
  return (
    <AppShell role="student">
      <AppHeader title="My Doubts" subtitle="All your lecture questions" />
      <PageContainer>
        <p className="text-sm text-gray-500 italic">View your doubts from lecture detail pages.</p>
      </PageContainer>
    </AppShell>
  )
}
