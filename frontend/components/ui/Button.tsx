'use client'

import { ButtonHTMLAttributes, forwardRef } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-yellow-400 hover:bg-yellow-500 text-black border border-yellow-400 hover:border-yellow-500 font-semibold',
  secondary:
    'bg-white hover:bg-gray-50 text-gray-800 border border-gray-300 hover:border-gray-400 font-medium',
  ghost:
    'bg-transparent hover:bg-gray-100 text-gray-700 border border-transparent font-medium',
  danger:
    'bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 hover:border-red-300 font-medium',
}

const sizeClasses: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs rounded',
  md: 'px-4 py-2 text-sm rounded',
  lg: 'px-5 py-2.5 text-sm rounded-md',
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'secondary',
    size = 'md',
    loading = false,
    disabled,
    className = '',
    children,
    ...props
  },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={[
        'inline-flex items-center justify-center gap-2 transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-yellow-400 focus:ring-offset-1',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...props}
    >
      {loading && (
        <span className="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
      )}
      {children}
    </button>
  )
})

export default Button
