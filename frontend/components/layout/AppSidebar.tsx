'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'

// ── Icon components (inline SVG, no dependency) ──────────────────────────────

function IconDashboard() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0h6" />
    </svg>
  )
}
function IconLectures() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.069A1 1 0 0121 8.862v6.276a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  )
}
function IconNotes() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}
function IconDoubts() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}
function IconBookmarks() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
    </svg>
  )
}
function IconUpload() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
    </svg>
  )
}
function IconFeedback() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  )
}
function IconHelp() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
  )
}
function IconLogout() {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  )
}

// ── Nav item config ──────────────────────────────────────────────────────────

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
}

const studentNav: NavItem[] = [
  { label: 'Dashboard',   href: '/student/dashboard',  icon: <IconDashboard /> },
  { label: 'My Lectures', href: '/student/lectures',    icon: <IconLectures /> },
  { label: 'Notes',       href: '/student/notes',       icon: <IconNotes /> },
  { label: 'Doubts',      href: '/student/doubts',      icon: <IconDoubts /> },
  { label: 'Bookmarks',   href: '/student/bookmarks',   icon: <IconBookmarks /> },
]

const teacherNav: NavItem[] = [
  { label: 'Dashboard',      href: '/teacher/dashboard',         icon: <IconDashboard /> },
  { label: 'My Lectures',    href: '/teacher/lectures',          icon: <IconLectures /> },
  { label: 'Upload Video',   href: '/teacher/upload',            icon: <IconUpload /> },
  { label: 'Student Doubts', href: '/teacher/doubts',            icon: <IconDoubts /> },
  { label: 'Feedback',       href: '/teacher/feedback',          icon: <IconFeedback /> },
  { label: 'Notes',          href: '/teacher/notes',             icon: <IconNotes /> },
]

interface AppSidebarProps {
  role: 'student' | 'teacher'
}

export default function AppSidebar({ role }: AppSidebarProps) {
  const pathname = usePathname()
  const { logout } = useAuth()
  const nav = role === 'student' ? studentNav : teacherNav

  function isActive(href: string) {
    if (href === '/') return pathname === '/'
    return pathname.startsWith(href)
  }

  return (
    <aside className="w-[220px] shrink-0 flex flex-col bg-white border-r border-gray-200 h-full z-10">
      {/* ── Brand ── */}
      <div className="flex flex-col items-center gap-2 px-5 py-6 border-b border-gray-100">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo.jpg"
          alt="CSJMU Kanpur logo"
          className="w-14 h-14 rounded-full object-cover border border-gray-200"
        />
        <div className="text-center">
          <p className="text-[13px] font-bold text-black tracking-tight leading-tight">VidyaRoom</p>
          <p className="text-[10px] text-gray-500 mt-0.5 leading-tight">CSJMU Kanpur</p>
        </div>
      </div>

      {/* ── Nav ── */}
      <nav className="flex-1 px-3 py-4 flex flex-col gap-0.5" aria-label="Main navigation">
        {nav.map((item) => {
          const active = isActive(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors',
                active
                  ? 'bg-yellow-50 text-yellow-700 font-semibold border border-yellow-200'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
              ].join(' ')}
              aria-current={active ? 'page' : undefined}
            >
              {item.icon}
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* ── Footer ── */}
      <div className="px-3 pb-5 border-t border-gray-100 pt-4 flex flex-col gap-2">
        <button
          className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors w-full text-left"
        >
          <IconHelp />
          Need Help?
        </button>
        <button
          onClick={() => logout()}
          className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-red-500 hover:bg-red-50 hover:text-red-700 transition-colors w-full text-left"
        >
          <IconLogout />
          Logout
        </button>
      </div>
    </aside>
  )
}
