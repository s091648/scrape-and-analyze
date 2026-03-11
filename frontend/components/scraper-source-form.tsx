'use client'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'

interface ScraperSourceFormData {
  source_type: 'rss' | 'blog'
  name: string
  url: string
  frequency: 'daily' | 'weekly'
  is_active: boolean
  selector_config?: { article_link: string; title: string; content: string }
}

const inputClass = "w-full h-14 px-5 rounded-lg border border-border bg-background text-sm transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
const labelClass = "block text-sm font-medium mb-1.5"
const selectClass = "w-full h-14 px-5 rounded-lg border border-border bg-background text-sm transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring appearance-none"

export function ScraperSourceForm({ onSubmit }: { onSubmit: (data: ScraperSourceFormData) => void }) {
  const [form, setForm] = useState<ScraperSourceFormData>({
    source_type: 'rss', name: '', url: '', frequency: 'daily', is_active: true,
  })

  return (
    <form onSubmit={e => { e.preventDefault(); onSubmit(form) }} className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className={labelClass} htmlFor="source_type">Source Type</label>
          <select
            id="source_type"
            className={selectClass}
            value={form.source_type}
            onChange={e => setForm(f => ({ ...f, source_type: e.target.value as 'rss' | 'blog' }))}
          >
            <option value="rss">RSS</option>
            <option value="blog">Blog</option>
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor="frequency">Frequency</label>
          <select
            id="frequency"
            className={selectClass}
            value={form.frequency}
            onChange={e => setForm(f => ({ ...f, frequency: e.target.value as 'daily' | 'weekly' }))}
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </div>
      </div>
      <div>
        <label className={labelClass} htmlFor="name">Name</label>
        <input
          id="name"
          className={inputClass}
          value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          placeholder="e.g. Hacker News"
        />
      </div>
      <div>
        <label className={labelClass} htmlFor="url">URL</label>
        <input
          id="url"
          className={inputClass}
          value={form.url}
          onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
          placeholder="https://..."
        />
      </div>
      {form.source_type === 'blog' && (
        <div className="rounded-2xl border border-border p-5 space-y-4">
          <p className="text-sm font-semibold">CSS Selectors</p>
          <div>
            <label className={labelClass} htmlFor="selector_article_link">Article Link</label>
            <input
              id="selector_article_link"
              className={inputClass}
              placeholder="a.post-link"
              onChange={e => setForm(f => ({
                ...f,
                selector_config: { title: '', content: '', ...f.selector_config, article_link: e.target.value },
              }))}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="selector_title">Title</label>
            <input
              id="selector_title"
              className={inputClass}
              placeholder="h1.post-title"
              onChange={e => setForm(f => ({
                ...f,
                selector_config: { article_link: '', content: '', ...f.selector_config, title: e.target.value },
              }))}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="selector_content">Content</label>
            <input
              id="selector_content"
              className={inputClass}
              placeholder=".post-content"
              onChange={e => setForm(f => ({
                ...f,
                selector_config: { article_link: '', title: '', ...f.selector_config, content: e.target.value },
              }))}
            />
          </div>
        </div>
      )}
      <Button type="submit" className="rounded-full h-10 px-6 gap-2">
        <Plus className="h-4 w-4" />
        Add Source
      </Button>
    </form>
  )
}
