'use client'

import UniversityWatermark from '@/components/layout/UniversityWatermark'

interface AuthLayoutProps {
  children: React.ReactNode
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4 relative overflow-hidden">
      <UniversityWatermark />
      <div className="w-full max-w-sm relative z-10">
        {/* Brand header */}
        <div className="flex flex-col items-center gap-3 mb-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.jpg"
            alt="CSJMU Kanpur"
            className="w-16 h-16 rounded-full object-cover border-2 border-gray-200"
          />
          <div className="text-center">
            <h1 className="text-xl font-bold text-black tracking-tight">VidyaRoom</h1>
            <p className="text-xs text-gray-500 mt-0.5">CSJMU Kanpur</p>
          </div>
        </div>
        {children}
      </div>
    </div>
  )
}
