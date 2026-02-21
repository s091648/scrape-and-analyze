'use client'
import { useState } from 'react'

interface FormData {
  source_type: 'rss' | 'blog'
  name: string
  url: string
  frequency: 'daily' | 'weekly'
  is_active: boolean
  selector_config?: { article_link: string; title: string; content: string }
}

export function ScraperSourceForm({ onSubmit }: { onSubmit: (data: FormData) => void }) {
  const [form, setForm] = useState<FormData>({
    source_type: 'rss', name: '', url: '', frequency: 'daily', is_active: true,
  })

  return (
    <form onSubmit={e => { e.preventDefault(); onSubmit(form) }} className="space-y-4">
      <div>
        <label htmlFor="source_type">Source Type</label>
        <select id="source_type" value={form.source_type}
          onChange={e => setForm(f => ({ ...f, source_type: e.target.value as 'rss' | 'blog' }))}>
          <option value="rss">RSS</option>
          <option value="blog">Blog</option>
        </select>
      </div>
      <div>
        <label>Name</label>
        <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
      </div>
      <div>
        <label>URL</label>
        <input value={form.url} onChange={e => setForm(f => ({ ...f, url: e.target.value }))} />
      </div>
      <div>
        <label>Frequency</label>
        <select value={form.frequency}
          onChange={e => setForm(f => ({ ...f, frequency: e.target.value as 'daily' | 'weekly' }))}>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
        </select>
      </div>
      {form.source_type === 'blog' && (
        <fieldset className="border p-3 rounded">
          <legend>CSS Selectors</legend>
          <div><label>Article Link</label>
            <input onChange={e => setForm(f => ({
              ...f, selector_config: { ...f.selector_config, article_link: e.target.value } as any
            }))} />
          </div>
          <div><label>Title</label>
            <input onChange={e => setForm(f => ({
              ...f, selector_config: { ...f.selector_config, title: e.target.value } as any
            }))} />
          </div>
          <div><label>Content</label>
            <input onChange={e => setForm(f => ({
              ...f, selector_config: { ...f.selector_config, content: e.target.value } as any
            }))} />
          </div>
        </fieldset>
      )}
      <button type="submit" className="px-4 py-2 bg-primary text-primary-foreground rounded">Save</button>
    </form>
  )
}
