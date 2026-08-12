import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'VidyaRoom',
  description: 'Real-time lecture translation and note-taking assistant',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
