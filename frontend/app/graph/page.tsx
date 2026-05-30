'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { KnowledgeGraph } from '@/components/features/graph/knowledge-graph'
import { Lock, Network } from 'lucide-react'
import { useI18n, useGuestMode, useTopic } from '@/lib/providers'
import { fetchArticles } from '@/lib/api/articles'

export default function GraphPage() {
  const { status } = useSession()
  const { t } = useI18n()
  const { isGuestMode } = useGuestMode()
  const { selectedTopicId } = useTopic()
  const isPaywall = status === 'unauthenticated' && !isGuestMode

  const [firstPageArticleIds, setFirstPageArticleIds] = useState<Set<string> | undefined>()

  useEffect(() => {
    if (!isGuestMode || !selectedTopicId) { setFirstPageArticleIds(undefined); return }
    fetchArticles({ page: 1, topic_id: selectedTopicId })
      .then(data => setFirstPageArticleIds(new Set(data.items.map(a => a.id))))
  }, [isGuestMode, selectedTopicId])

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center gap-3 border-b border-border pb-6">
        <Network className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-bold leading-none">{t('graph.title')}</h1>
      </div>

      {isGuestMode && (
        <p className="text-sm text-muted-foreground">
          {t('guest.graphLimitedPreview')}{' '}
          <Link href="/login" className="font-medium text-primary underline underline-offset-4">
            {t('login.signIn')}
          </Link>
        </p>
      )}

      <div className="relative flex-1">
        <KnowledgeGraph articleIdFilter={isGuestMode ? firstPageArticleIds : undefined} />

        {isPaywall && (
          <div className="absolute inset-0 backdrop-blur-sm bg-background/60 flex flex-col items-center justify-center gap-4 rounded-xl">
            <div className="flex items-center justify-center h-14 w-14 rounded-full border border-border bg-background shadow-sm">
              <Lock className="h-6 w-6 text-muted-foreground" />
            </div>
            <div className="text-center space-y-1.5">
              <p className="text-sm font-medium">{t('graph.signInToExplore')}</p>
              <p className="text-sm text-muted-foreground">
                <Link href="/login" className="font-medium text-primary underline underline-offset-4">{t('login.signIn')}</Link>
                {' '}{t('graph.signInToAccess')}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
