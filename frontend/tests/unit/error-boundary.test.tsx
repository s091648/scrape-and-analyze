import { describe, it, expect, vi } from 'vitest'
import React from 'react'
import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from '@/components/common/error-boundary'

function ThrowingChild(): React.ReactNode {
  throw new Error('Network error')
}

describe('ErrorBoundary', () => {
  it('renders fallback UI when child throws', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    )
    expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument()
    consoleSpy.mockRestore()
  })
})