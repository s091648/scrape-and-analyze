'use client'

import { GrafanaPanel } from '@/components/features/monitoring/grafana-panel'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'

interface MonitoringContentProps {
  grafanaUrl: string
}

export function MonitoringContent({ grafanaUrl }: MonitoringContentProps) {
  const { t } = useI18n()
  const Panel = (props: Omit<React.ComponentProps<typeof GrafanaPanel>, 'grafanaUrl'>) => (
    <GrafanaPanel {...props} grafanaUrl={grafanaUrl} />
  )

  return (
    <div className="max-w-7xl space-y-6">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.monitoring')}</h1>
      </div>

      <Tabs defaultValue="operations">
        <TabsList>
          <TabsTrigger value="operations">{t('admin.operations')}</TabsTrigger>
          <TabsTrigger value="logs">{t('admin.logs')}</TabsTrigger>
          <TabsTrigger value="traces">{t('admin.traces')}</TabsTrigger>
        </TabsList>

        {/* ── Operations tab ─────────────────────────────────────────────── */}
        <TabsContent value="operations">
          <div className="space-y-4">
            {/* Row 1: 4 stat panels */}
            <div className="grid grid-cols-4 gap-3 mt-4">
              <Panel dashboardUid="scraper-ops-001" panelId={1} title="Total Runs (24h)" height={120} />
              <Panel dashboardUid="scraper-ops-001" panelId={2} title="Recent Run Duration (p100)" height={120} />
              <Panel dashboardUid="scraper-ops-001" panelId={3} title="Avg Duration (p50)" height={120} />
              <Panel dashboardUid="scraper-ops-001" panelId={4} title="Error Count (24h)" height={120} />
            </div>

            {/* Row 2: 4 panels */}
            <div className="grid grid-cols-4 gap-3">
              <Panel dashboardUid="scraper-ops-001" panelId={5} title="New Articles (24h)" height={120} />
              <Panel dashboardUid="scraper-ops-001" panelId={6} title="Duplicate Rate %" height={120} />
              <Panel dashboardUid="scraper-ops-001" panelId={7} title="Failed Articles (24h)" height={120} />
              <Panel dashboardUid="scraper-ops-001" panelId={8} title="New / Run Ratio" height={120} />
            </div>

            {/* Row 3: 2 time series */}
            <div className="grid grid-cols-2 gap-3">
              <Panel dashboardUid="scraper-ops-001" panelId={9} title="Article Volume Over Time" height={240} />
              <Panel dashboardUid="scraper-ops-001" panelId={10} title="Run Duration Over Time" height={240} />
            </div>

            {/* Row 4: 2 bar charts */}
            <div className="grid grid-cols-2 gap-3">
              <Panel dashboardUid="scraper-ops-001" panelId={11} title="New Articles by Source" height={240} />
              <Panel dashboardUid="scraper-ops-001" panelId={12} title="Errors by Type" height={240} />
            </div>
          </div>
        </TabsContent>

        {/* ── Logs tab ───────────────────────────────────────────────────── */}
        <TabsContent value="logs">
          <div className="space-y-4">
            {/* Row 1: timeseries + 2 stats */}
            <div className="grid grid-cols-6 gap-3 mt-4">
              <Panel dashboardUid="scraper-logs-001" panelId={1} title="Log Volume by Level" height={180} from="now-6h" className="col-span-4" />
              <Panel dashboardUid="scraper-logs-001" panelId={2} title="Error Count (1h)" height={180} from="now-6h" className="col-span-1" />
              <Panel dashboardUid="scraper-logs-001" panelId={3} title="Warning Count (1h)" height={180} from="now-6h" className="col-span-1" />
            </div>

            {/* Row 2: execution timeline full width */}
            <div>
              <Panel dashboardUid="scraper-logs-001" panelId={4} title="Execution Timeline" height={300} from="now-6h" />
            </div>

            {/* Row 3: error & failure logs full width */}
            <div>
              <Panel dashboardUid="scraper-logs-001" panelId={5} title="Error & Failure Logs" height={300} from="now-6h" />
            </div>

            {/* Row 4: two columns */}
            <div className="grid grid-cols-2 gap-3">
              <Panel dashboardUid="scraper-logs-001" panelId={6} title="Article Success Logs" height={240} from="now-6h" />
              <Panel dashboardUid="scraper-logs-001" panelId={7} title="Article Failure Logs" height={240} from="now-6h" />
            </div>
          </div>
        </TabsContent>

        {/* ── Traces tab ─────────────────────────────────────────────────── */}
        <TabsContent value="traces">
          <div className="space-y-4">
            {/* Row 1: 3 stat panels */}
            <div className="grid grid-cols-3 gap-3 mt-4">
              <Panel dashboardUid="scraper-traces-001" panelId={1} title="Traces (24h)" height={120} />
              <Panel dashboardUid="scraper-traces-001" panelId={2} title="LLM Latency P95" height={120} />
              <Panel dashboardUid="scraper-traces-001" panelId={3} title="Error Spans (24h)" height={120} />
            </div>

            {/* Row 2: span rate timeline full width */}
            <div>
              <Panel dashboardUid="scraper-traces-001" panelId={4} title="Span Rate by Operation" height={240} />
            </div>

            {/* Row 3: trace search full width */}
            <div>
              <Panel dashboardUid="scraper-traces-001" panelId={5} title="Recent Traces" height={400} />
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
