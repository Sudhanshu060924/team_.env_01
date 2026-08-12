'use client'

interface AvatarProps {
  name: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizeClasses = {
  sm: 'w-7 h-7 text-xs',
  md: 'w-9 h-9 text-sm',
  lg: 'w-11 h-11 text-base',
}

function initials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
}

export default function Avatar({ name, size = 'md', className = '' }: AvatarProps) {
  return (
    <div
      aria-label={name}
      className={[
        'inline-flex items-center justify-center rounded-full font-semibold',
        'bg-gray-800 text-white shrink-0',
        sizeClasses[size],
        className,
      ].join(' ')}
    >
      {initials(name)}
    </div>
  )
}
