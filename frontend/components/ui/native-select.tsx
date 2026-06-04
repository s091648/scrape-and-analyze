import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface NativeSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  /** 'md' = h-9 text-sm (default), 'sm' = compact text-xs */
  size?: 'sm' | 'md'
}

export const NativeSelect = forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, size = 'md', children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring',
        size === 'md' && 'h-9 px-2 text-sm',
        size === 'sm' && 'px-1.5 py-0.5 text-xs rounded',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
)
NativeSelect.displayName = 'NativeSelect'
