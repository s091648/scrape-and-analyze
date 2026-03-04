'use client'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { KnowledgeGraph } from '@/components/knowledge-graph'
import { Lock } from 'lucide-react'

export default function GraphPage() {
  const { status } = useSession()
  const isGuest = status === 'unauthenticated'

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center gap-3 border-b border-border pb-6">
        <h1 className="text-2xl font-bold leading-none">Knowledge Graph</h1>
      </div>

      <div className="relative flex-1">
        <KnowledgeGraph />

        {isGuest && (
          <div className="absolute inset-0 backdrop-blur-sm bg-background/60 flex flex-col items-center justify-center gap-4 rounded-xl">
            <div className="flex items-center justify-center h-14 w-14 rounded-full border border-border bg-background shadow-sm">
              <Lock className="h-6 w-6 text-muted-foreground" />
            </div>
            <div className="text-center space-y-1.5">
              <p className="text-sm font-medium">知識圖譜需要登入才能查看</p>
              <p className="text-sm text-muted-foreground">
                <Link href="/login" className="font-medium text-primary underline underline-offset-4">登入</Link>
                {' '}後即可探索完整內容
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
