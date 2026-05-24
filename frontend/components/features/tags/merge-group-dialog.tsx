'use client'
import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { TagGroupOut } from '@/lib/api/tags'
import { mergeTagGroups } from '@/lib/api/tags'

interface MergeForm {
  name: string
  display_name: string
  color_hex: string
  description: string
}

interface Props {
  groupA: TagGroupOut
  groupB: TagGroupOut
  token: string
  onMerged: (result: TagGroupOut) => void
  onClose: () => void
}

export function MergeGroupDialog({ groupA, groupB, token, onMerged, onClose }: Props) {
  const [form, setForm] = useState<MergeForm>({
    name: groupA.name,
    display_name: groupA.display_name,
    color_hex: groupA.color_hex ?? '',
    description: groupA.description ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function fillFrom(group: TagGroupOut) {
    setForm({
      name: group.name,
      display_name: group.display_name,
      color_hex: group.color_hex ?? '',
      description: group.description ?? '',
    })
  }

  const allTags = [
    ...groupA.tags,
    ...groupB.tags.filter(t => !groupA.tags.some(a => a.id === t.id)),
  ].sort((a, b) => b.article_count - a.article_count)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name.trim() || !form.display_name.trim()) return
    setSaving(true)
    setError('')
    try {
      const result = await mergeTagGroups({
        group_a_id: groupA.id,
        group_b_id: groupB.id,
        result_name: form.name.trim(),
        result_display_name: form.display_name.trim(),
        result_color_hex: form.color_hex.trim() || undefined,
        result_description: form.description.trim() || undefined,
      }, token)
      onMerged(result)
    } catch (err: any) {
      setError(err.message ?? 'Error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <form
        className="bg-card border border-border rounded-xl shadow-lg w-full max-w-5xl flex flex-col max-h-[90vh]"
        onClick={e => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border shrink-0">
          <div>
            <h2 className="text-sm font-semibold">Merge Tag Groups</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {groupA.display_name} + {groupB.display_name}
            </p>
          </div>
          <button type="button" onClick={onClose}>
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 min-h-0 divide-x divide-border overflow-hidden">
          {/* Left: form */}
          <div className="flex-1 p-5 space-y-4 overflow-y-auto">
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">Quick fill from</p>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => fillFrom(groupA)}>
                  {groupA.display_name}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => fillFrom(groupB)}>
                  {groupB.display_name}
                </Button>
              </div>
            </div>

            {[
              { key: 'name', label: 'Name (slug) *', required: true },
              { key: 'display_name', label: 'Display Name *', required: true },
              { key: 'color_hex', label: 'Color', required: false, placeholder: '#3b82f6' },
              { key: 'description', label: 'Description', required: false },
            ].map(({ key, label, required, placeholder }) => (
              <div key={key} className="space-y-1">
                <label className="text-xs text-muted-foreground">{label}</label>
                {key === 'color_hex' ? (
                  <div className="flex gap-2 items-center">
                    <div className="relative h-[34px] w-[34px] shrink-0 cursor-pointer rounded-md border border-border overflow-hidden">
                      <span className="absolute inset-0" style={{ backgroundColor: form.color_hex || '#e5e7eb' }} />
                      <input
                        type="color"
                        value={/^#[0-9a-fA-F]{6}$/.test(form.color_hex) ? form.color_hex : '#e5e7eb'}
                        onChange={e => setForm(prev => ({ ...prev, color_hex: e.target.value }))}
                        className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                      />
                    </div>
                    <input
                      className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      value={form.color_hex}
                      placeholder={placeholder}
                      onChange={e => setForm(prev => ({ ...prev, color_hex: e.target.value }))}
                    />
                  </div>
                ) : (
                  <input
                    className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                    value={(form as any)[key]}
                    placeholder={placeholder}
                    onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
                    required={required}
                  />
                )}
              </div>
            ))}

            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>

          {/* Right: live preview */}
          <div className="flex-1 p-5 space-y-3 overflow-y-auto bg-muted/20">
            <p className="text-xs text-muted-foreground font-medium">Preview</p>
            <div
              className="rounded-xl border border-border bg-card p-4 space-y-3"
              style={form.color_hex ? { borderColor: form.color_hex } : undefined}
            >
              <div className="flex items-center gap-2">
                {form.color_hex && (
                  <span
                    className="h-3 w-3 rounded-full shrink-0"
                    style={{ backgroundColor: form.color_hex }}
                  />
                )}
                <span className="font-semibold text-sm">{form.display_name || '—'}</span>
                <span className="text-xs text-muted-foreground">{allTags.length} tags</span>
              </div>
              {form.description && (
                <p className="text-xs text-muted-foreground">{form.description}</p>
              )}
              <div className="flex flex-wrap gap-1.5">
                {allTags.map(tag => (
                  <span
                    key={tag.id}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-border bg-muted/50 text-xs"
                  >
                    {tag.name}
                    <span className="text-muted-foreground tabular-nums [font-variant-ligatures:none]">({tag.article_count})</span>
                  </span>
                ))}
                {allTags.length === 0 && (
                  <span className="text-xs text-muted-foreground italic">No tags yet</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-5 border-t border-border shrink-0">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button type="submit" size="sm" disabled={saving}>
            {saving ? 'Merging...' : 'Merge Groups'}
          </Button>
        </div>
      </form>
    </div>
  )
}
