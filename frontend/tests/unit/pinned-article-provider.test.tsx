import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PinnedArticleProvider, usePinnedArticle } from '@/lib/providers/pinned-article-provider'

function Consumer() {
  const {
    pinnedArticles, pinArticles, areAllPinned, togglePinnedArticle, removePinnedArticle,
    pinnedGroups, pinGroup, toggleGroupArticle, removeGroup, isPinned,
  } = usePinnedArticle()
  return (
    <div>
      <span data-testid="count">{pinnedArticles.length}</span>
      <span data-testid="ids">{pinnedArticles.map(a => a.id).join(',')}</span>
      <span data-testid="all-pinned-a1-a2">{String(areAllPinned(['a1', 'a2']))}</span>
      <span data-testid="all-pinned-empty">{String(areAllPinned([]))}</span>
      <span data-testid="group-count">{pinnedGroups.length}</span>
      <span data-testid="group-ids">{pinnedGroups.map(g => g.id).join(',')}</span>
      <span data-testid="a1-pinned">{String(isPinned('a1'))}</span>
      <span data-testid="a2-pinned">{String(isPinned('a2'))}</span>
      <button onClick={() => pinArticles([{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }])}>
        pin-a1-a2
      </button>
      <button onClick={() => pinArticles([{ id: 'a1', title: 'Paper One' }, { id: 'a3', title: 'Paper Three' }])}>
        pin-a1-a3
      </button>
      <button onClick={() => togglePinnedArticle({ id: 'a1', title: 'Paper One' })}>toggle-a1</button>
      <button onClick={() => removePinnedArticle('a1')}>remove-a1</button>
      <button onClick={() => pinGroup({
        id: 'group-1',
        dateLabel: '6/29',
        articles: [{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }],
      })}>
        pin-group-1
      </button>
      <button onClick={() => toggleGroupArticle('group-1', 'a1')}>toggle-group-1-a1</button>
      <button onClick={() => toggleGroupArticle('group-1', 'a2')}>toggle-group-1-a2</button>
      <button onClick={() => removeGroup('group-1')}>remove-group-1</button>
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

describe('PinnedArticleProvider — pinnedGroups (2026-07-14, US10)', () => {
  it('pinGroup adds the group and pins every one of its articles', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-group-1'))
    expect(screen.getByTestId('group-count').textContent).toBe('1')
    expect(screen.getByTestId('group-ids').textContent).toBe('group-1')
    expect(screen.getByTestId('count').textContent).toBe('2')
    expect(screen.getByTestId('a1-pinned').textContent).toBe('true')
    expect(screen.getByTestId('a2-pinned').textContent).toBe('true')
  })

  it('toggleGroupArticle unpins just that one article, leaving the group and its sibling article pinned', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-group-1'))
    fireEvent.click(screen.getByText('toggle-group-1-a2'))
    expect(screen.getByTestId('a1-pinned').textContent).toBe('true')
    expect(screen.getByTestId('a2-pinned').textContent).toBe('false')
    expect(screen.getByTestId('group-count').textContent).toBe('1')
  })

  it('toggleGroupArticle re-pins an article that was previously excluded', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-group-1'))
    fireEvent.click(screen.getByText('toggle-group-1-a2'))
    fireEvent.click(screen.getByText('toggle-group-1-a2'))
    expect(screen.getByTestId('a2-pinned').textContent).toBe('true')
  })

  it('removes the group entirely once every one of its articles has been unchecked', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-group-1'))
    fireEvent.click(screen.getByText('toggle-group-1-a1'))
    fireEvent.click(screen.getByText('toggle-group-1-a2'))
    expect(screen.getByTestId('group-count').textContent).toBe('0')
    expect(screen.getByTestId('a1-pinned').textContent).toBe('false')
    expect(screen.getByTestId('a2-pinned').textContent).toBe('false')
  })

  it('removeGroup unpins every article in the group and deletes it', () => {
    renderConsumer()
    fireEvent.click(screen.getByText('pin-group-1'))
    fireEvent.click(screen.getByText('remove-group-1'))
    expect(screen.getByTestId('group-count').textContent).toBe('0')
    expect(screen.getByTestId('count').textContent).toBe('0')
  })
})
