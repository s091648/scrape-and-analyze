'use client'
import { useSearchParams, useRouter } from 'next/navigation'

export function usePagination() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const page = parseInt(searchParams.get('page') || '1', 10)
  const sort = searchParams.get('sort') || 'scraped_at'
  const order = searchParams.get('order') || 'desc'

  function setPage(newPage: number) {
    const params = new URLSearchParams(searchParams.toString())
    params.set('page', String(newPage))
    router.push(`?${params.toString()}`)
  }

  function setSort(newSort: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set('sort', newSort)
    params.set('page', '1')
    router.push(`?${params.toString()}`)
  }

  return { page, sort, order, setPage, setSort }
}
