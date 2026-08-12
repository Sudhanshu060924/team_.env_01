'use client'
import AppShell from '@/components/layout/AppShell'
import AppHeader from '@/components/layout/AppHeader'
import PageContainer from '@/components/layout/PageContainer'

export default function StudentBookmarksPage() {
  return (
    <AppShell role="student">
      <AppHeader title="Bookmarks" subtitle="Your saved lectures" />
      <PageContainer>
        <p className="text-sm text-gray-500 italic">Bookmarked lectures will appear here.</p>
      </PageContainer>
    </AppShell>
  )
}
