import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface ArticleCardProps {
  id: string
  title: string
  source: string
  published_at: string | null
  scraped_at: string | null
  url: string
}

export function ArticleCard({ title, source, published_at, scraped_at, url }: ArticleCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <a href={url} target="_blank" rel="noreferrer" className="hover:underline">{title}</a>
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground flex gap-4">
        <span>{source}</span>
        {published_at && <span>Published: {new Date(published_at).toLocaleDateString()}</span>}
        {scraped_at && <span>Scraped: {new Date(scraped_at).toLocaleDateString()}</span>}
      </CardContent>
    </Card>
  )
}
