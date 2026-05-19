'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Skeleton } from '@/components/ui/skeleton'
import { useTopic, useI18n } from '@/lib/providers'
import {
  fetchTagGroups, fetchPendingSuggestions,
  type TagGroupOut, type SuggestionOut,
} from '@/lib/api/tags'
import { TagGroupCard } from '@/components/features/tags/tag-group-card'
import { PendingSuggestions } from '@/components/features/tags/pending-suggestions'

export default function TagsPage() {
  const { data: session } = useSession()
  const token = (session as any)?.accessToken as string | undefined
  const isAdmin = (session?.user as any)?.role === 'admin'
  const { selectedTopic } = useTopic()
  const { t } = useI18n()

  const [groups, setGroups] = useState<TagGroupOut[]>([])
  const [suggestions, setSuggestions] = useState<SuggestionOut[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const topicId = selectedTopic?.id
    Promise.all([
      fetchTagGroups(topicId),
      isAdmin && token ? fetchPendingSuggestions(token) : Promise.resolve([]),
    ])
      .then(([g, s]) => { setGroups(g); setSuggestions(s) })
      .finally(() => setLoading(false))
  }, [selectedTopic?.id, isAdmin, token])

  return (
    <div className="container mx-auto px-6 pt-24 pb-16 max-w-4xl space-y-8">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('tags.title')}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t('tags.description')}
          {isAdmin && t('tags.adminDesc')}
        </p>
      </div>

      {isAdmin && suggestions.length > 0 && (
        <PendingSuggestions
          suggestions={suggestions}
          token={token!}
          onResolved={id => setSuggestions(prev => prev.filter(s => s.id !== id))}
        />
      )}

      {loading ? (
        <div className="space-y-4">
          {[0, 1, 2].map(i => (
            <div key={i} className="rounded-xl border border-border bg-card p-5 space-y-3">
              <Skeleton className="h-4 w-32" />
              <div className="flex gap-2">
                <Skeleton className="h-6 w-20 rounded-full" />
                <Skeleton className="h-6 w-16 rounded-full" />
                <Skeleton className="h-6 w-24 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      ) : groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('tags.noGroups')}</p>
      ) : (
        <div className="space-y-4">
          {groups.map(group => (
            <TagGroupCard
              key={group.id}
              group={group}
              isAdmin={isAdmin}
              token={token}
              onDeleted={groupId => setGroups(prev => prev.filter(g => g.id !== groupId))}
              onTagRenamed={(groupId, tagId, name) => setGroups(prev =>
                prev.map(g => g.id === groupId
                  ? { ...g, tags: g.tags.map(t => t.id === tagId ? { ...t, name } : t) }
                  : g
                )
              )}
              onTagDeleted={(groupId, tagId) => setGroups(prev =>
                prev.map(g => g.id === groupId
                  ? { ...g, tags: g.tags.filter(t => t.id !== tagId) }
                  : g
                )
              )}
            />
          ))}
        </div>
      )}
    </div>
  )
}
