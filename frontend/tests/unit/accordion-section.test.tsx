import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

describe('AccordionSection', () => {
  const defaultProps = {
    title: 'Test Section',
    children: <p>Section content</p>,
  }

  it('renders the title', async () => {
    const { AccordionSection } = await import('@/components/ui/accordion-section')
    render(<AccordionSection {...defaultProps} />)
    expect(screen.getByText('Test Section')).toBeInTheDocument()
  })

  it('shows children by default (defaultOpen=true)', async () => {
    const { AccordionSection } = await import('@/components/ui/accordion-section')
    render(<AccordionSection {...defaultProps} />)
    expect(screen.getByText('Section content')).toBeInTheDocument()
  })

  it('hides children when defaultOpen=false', async () => {
    const { AccordionSection } = await import('@/components/ui/accordion-section')
    render(<AccordionSection {...defaultProps} defaultOpen={false} />)
    expect(screen.queryByText('Section content')).not.toBeInTheDocument()
  })

  it('toggles children visibility on click', async () => {
    const { AccordionSection } = await import('@/components/ui/accordion-section')
    render(<AccordionSection {...defaultProps} />)
    const button = screen.getByRole('button')
    fireEvent.click(button)
    expect(screen.queryByText('Section content')).not.toBeInTheDocument()
    fireEvent.click(button)
    expect(screen.getByText('Section content')).toBeInTheDocument()
  })

  it('renders badge when provided', async () => {
    const { AccordionSection } = await import('@/components/ui/accordion-section')
    render(<AccordionSection {...defaultProps} badge={5} />)
    expect(screen.getByText('5')).toBeInTheDocument()
  })
})
