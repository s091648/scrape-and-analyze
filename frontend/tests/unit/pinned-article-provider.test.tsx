import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PinnedArticleProvider, usePinnedArticle } from '@/lib/providers/pinned-article-provider'

function Consumer() {
  const { pinnedArticles, pinArticles, areAllPinned, togglePinnedArticle, removePinnedArticle } = usePinnedArticle()
  return (
    <div>
      <span data-testid="count">{pinnedArticles.length}</span>
      <span data-testid="ids">{pinnedArticles.map(a => a.id).join(',')}</span>
      <span data-testid="all-pinned-a1-a2">{String(areAllPinned(['a1', 'a2']))}</span>
      <span data-testid="all-pinned-empty">{String(areAllPinned([]))}</span>
      <button onClick={() => pinArticles([{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }])}>
        pin-a1-a2
      </button>
      <button onClick={() => pinArticles([{ id: 'a1', title: 'Paper One' }, { id: 'a3', title: 'Paper Three' }])}>
        pin-a1-a3
      </button>
      <button onClick={() => togglePinnedArticle({ id: 'a1', title: 'Paper One' })}>toggle-a1</button>
      <button onClick={() => removePinnedArticle('a1')}>remove-a1</button>
    </div>
  )
}

function renderConsumer() {
  return render(
    <PinnedArticleProvider>
      <Consumer />
    </PinnedArticleProvider>
  )
}

describe('PinnedArticleProvider — pinArticles / areAllPinned (2026-07-12, US7)', () => {
  it('pinArticles adds all given articles when none are pinned yet', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-a1-a2'))
    expect(screen.getByTestId('count').textContent).toBe('2')
    expect(screen.getByTestId('ids').textContent).toBe('a1,a2')
  })

  it('pinArticles does not duplicate an article that is already pinned', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-a1-a2'))
    fireEvent.click(screen.getByText('pin-a1-a3'))
    expect(screen.getByTestId('count').textContent).toBe('3')
    expect(screen.getByTestId('ids').textContent).toBe('a1,a2,a3')
  })

  it('areAllPinned returns false when only some ids are pinned', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('toggle-a1'))
    expect(screen.getByTestId('all-pinned-a1-a2').textContent).toBe('false')
  })

  it('areAllPinned returns true only once every given id is pinned', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-a1-a2'))
    expect(screen.getByTestId('all-pinned-a1-a2').textContent).toBe('true')
  })

  it('areAllPinned returns false for an empty id list (vacuously not "all pinned")', () => {
    renderConsumer()
    expect(screen.getByTestId('all-pinned-empty').textContent).toBe('false')
  })

  it('existing per-article API (toggle/remove) still works unchanged', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('toggle-a1'))
    expect(screen.getByTestId('count').textContent).toBe('1')
    fireEvent.click(screen.getByText('remove-a1'))
    expect(screen.getByTestId('count').textContent).toBe('0')
  })
})
