'use client'

interface ProgressBarProps {
  value: number      // 0–100
  className?: string
  size?: 'sm' | 'md'
}

export default function ProgressBar({ value, className = '', size = 'sm' }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value))
  const h = size === 'sm' ? 'h-1' : 'h-1.5'
  return (
    <div className={['w-full bg-gray-200 rounded-full overflow-hidden', h, className].join(' ')}>
      <div
        className={['bg-yellow-400 rounded-full transition-all', h].join(' ')}
        style={{ width: `${clamped}%` }}
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
      />
    </div>
  )
}
