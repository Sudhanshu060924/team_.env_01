'use client'

import { useState, useEffect } from 'react'
import AppSidebar from './AppSidebar'
import UniversityWatermark from './UniversityWatermark'
import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/navigation'

interface AppShellProps {
  children: React.ReactNode
  role: 'student' | 'teacher'
}

function MenuIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

export default function AppShell({ children, role }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()

  // Close drawer on resize to desktop
  useEffect(() => {
    const handler = () => {
      if (window.innerWidth >= 768) setDrawerOpen(false)
    }
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  // Auth guard
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login')
    }
  }, [isLoading, isAuthenticated, router])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500 text-sm">
        Loading…
      </div>
    )
  }
  if (!user) return null

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden relative">
      <UniversityWatermark />

      {/* ── Desktop sidebar ── */}
      <div className="hidden md:flex md:flex-col md:h-full relative z-10">
        <AppSidebar role={role} />
      </div>

      {/* ── Mobile drawer backdrop ── */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/30 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Mobile sidebar drawer ── */}
      <div
        className={[
          'fixed top-0 left-0 h-full z-30 md:hidden transition-transform duration-200',
          drawerOpen ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
      >
        <AppSidebar role={role} />
      </div>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
        {/* Mobile top bar with hamburger */}
        <div className="md:hidden flex items-center gap-3 h-12 px-4 bg-white border-b border-gray-200 shrink-0">
          <button
            onClick={() => setDrawerOpen((o) => !o)}
            className="p-1 text-gray-600 hover:text-gray-900"
            aria-label={drawerOpen ? 'Close menu' : 'Open menu'}
          >
            {drawerOpen ? <CloseIcon /> : <MenuIcon />}
          </button>
          <span className="font-bold text-sm text-black">VidyaRoom</span>
        </div>

        {children}
      </div>
    </div>
  )
}
