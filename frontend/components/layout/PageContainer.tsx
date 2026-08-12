'use client'

interface PageContainerProps {
  children: React.ReactNode
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  className?: string
}

const maxWidthClasses = {
  sm: 'max-w-2xl',
  md: 'max-w-4xl',
  lg: 'max-w-6xl',
  xl: 'max-w-7xl',
  full: 'max-w-none',
}

export default function PageContainer({
  children,
  maxWidth = 'lg',
  className = '',
}: PageContainerProps) {
  return (
    <div className={['flex-1 overflow-y-auto', className].join(' ')}>
      <div className={['mx-auto px-6 py-8', maxWidthClasses[maxWidth]].join(' ')}>
        {children}
      </div>
    </div>
  )
}
