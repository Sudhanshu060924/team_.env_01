'use client'

type BadgeVariant = 'default' | 'completed' | 'live' | 'notStarted' | 'yellow' | 'gray' | 'green' | 'red'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
}

const variantClasses: Record<BadgeVariant, string> = {
  default:    'bg-gray-100 text-gray-700 border border-gray-200',
  completed:  'bg-green-50 text-green-700 border border-green-200',
  live:       'bg-yellow-50 text-yellow-700 border border-yellow-300',
  notStarted: 'bg-gray-50 text-gray-600 border border-gray-200',
  yellow:     'bg-yellow-100 text-yellow-800 border border-yellow-200',
  gray:       'bg-gray-100 text-gray-600 border border-gray-200',
  green:      'bg-green-50 text-green-700 border border-green-200',
  red:        'bg-red-50 text-red-700 border border-red-200',
}

export default function Badge({ variant = 'default', children, className = '' }: BadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold',
        variantClasses[variant],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {children}
    </span>
  )
}
