interface FailedTask {
  id: string; task_type: string; article_url: string | null
  exception_type: string | null; exception_message: string | null
  failed_at: string | null; resolved: boolean
}

export function FailedTaskList({ items }: { items: FailedTask[] }) {
  if (items.length === 0) return null
  return (
    <section className="mt-8">
      <h2 className="text-xl font-semibold mb-4 text-destructive">Failed Tasks ({items.length})</h2>
      <ul className="space-y-2">
        {items.map(t => (
          <li key={t.id} className="border rounded p-3 text-sm">
            <p className="font-medium">{t.task_type}: {t.article_url}</p>
            <p className="text-muted-foreground">{t.exception_message}</p>
            {t.failed_at && <p className="text-xs">{new Date(t.failed_at).toLocaleString()}</p>}
          </li>
        ))}
      </ul>
    </section>
  )
}
