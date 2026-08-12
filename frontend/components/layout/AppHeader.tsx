'use client'

import Avatar from '@/components/ui/Avatar'
import { useAuth } from '@/hooks/useAuth'

interface AppHeaderProps {
  title?: string
  subtitle?: string
  children?: React.ReactNode
}

function IconBell() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  )
}

export default function AppHeader({ title, subtitle, children }: AppHeaderProps) {
  const { user } = useAuth()

  return (
    <header className="h-14 shrink-0 bg-white border-b border-gray-200 flex items-center px-6 gap-4 z-10 relative">
      {/* Left — title area */}
      <div className="flex-1 min-w-0">
        {title && (
          <div>
            <h1 className="text-base font-semibold text-black leading-tight truncate">{title}</h1>
            {subtitle && (
              <p className="text-xs text-gray-500 leading-tight">{subtitle}</p>
            )}
          </div>
        )}
        {children && !title && children}
      </div>

      {/* Extra content (e.g. lecture title + badge) */}
      {children && title && <div className="flex-1">{children}</div>}

      {/* Right — bell + user */}
      <div className="flex items-center gap-3 shrink-0">
        <button
          className="relative p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors"
          aria-label="Notifications"
        >
          <IconBell />
        </button>

        {user && (
          <div className="flex items-center gap-2">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-semibold text-black leading-tight">{user.name}</p>
              <p className="text-[11px] text-gray-500 capitalize leading-tight">{user.role}</p>
            </div>
            <Avatar name={user.name} size="sm" />
          </div>
        )}
      </div>
    </header>
  )
}
