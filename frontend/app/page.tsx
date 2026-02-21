'use client'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api-fetch'
import { ArticleCard } from '@/components/article-card'
import { usePagination } from '@/hooks/use-pagination'

interface Article {
  id: string; title: string; source: string
  published_at: string | null; scraped_at: string | null; url: string
}

export default function HomePage() {
  const { page, sort, order, setPage } = usePagination()
  const [articles, setArticles] = useState<Article[]>([])
  const [total, setTotal] = useState(0)

  useEffect(() => {
    apiFetch(`/articles?page=${page}&sort=${sort}&order=${order}`)
      .then(r => r.json())
      .then(data => { setArticles(data.items); setTotal(data.total) })
  }, [page, sort, order])

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Articles ({total})</h1>
      <div className="grid gap-4">
        {articles.map(a => <ArticleCard key={a.id} {...a} />)}
      </div>
      <div className="flex gap-2 justify-center mt-4">
        {page > 1 && <button onClick={() => setPage(page - 1)}>Previous</button>}
        <span>Page {page} of {totalPages}</span>
        {page < totalPages && <button onClick={() => setPage(page + 1)}>Next</button>}
      </div>
    </div>
  )
}
