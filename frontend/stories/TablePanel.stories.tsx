import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { TablePanel } from '../components/ui/table-panel'
import { TooltipProvider } from '../components/ui/tooltip'

const SAMPLE_COLUMNS = [
  { key: 'name',   label: 'Name' },
  { key: 'value',  label: 'Value',  align: 'right' as const },
  { key: 'status', label: 'Status' },
]

const SAMPLE_ROWS = (
  <>
    <tr className="border-b border-border hover:bg-muted/30">
      <td className="px-2 py-1">Article Alpha</td>
      <td className="px-2 py-1 text-right tabular-nums">42</td>
      <td className="px-2 py-1 text-muted-foreground">active</td>
    </tr>
    <tr className="border-b border-border hover:bg-muted/30">
      <td className="px-2 py-1">Article Beta</td>
      <td className="px-2 py-1 text-right tabular-nums">17</td>
      <td className="px-2 py-1 text-muted-foreground">inactive</td>
    </tr>
    <tr className="border-b border-border last:border-0 hover:bg-muted/30">
      <td className="px-2 py-1">Article Gamma</td>
      <td className="px-2 py-1 text-right tabular-nums">99</td>
      <td className="px-2 py-1 text-muted-foreground">active</td>
    </tr>
  </>
)

const meta: Meta<typeof TablePanel> = {
  title: 'UI/TablePanel',
  component: TablePanel,
  decorators: [Story => <TooltipProvider><Story /></TooltipProvider>],
  args: {
    title: 'Sample Table',
    columns: SAMPLE_COLUMNS,
    height: 300,
  },
}
export default meta
type Story = StoryObj<typeof TablePanel>

export const Loading: Story = {
  args: { loading: true },
}

export const NotConfigured: Story = {
  args: { placeholder: 'Grafana not configured' },
}

export const ErrorState: Story = {
  args: { placeholder: 'Failed to load data', placeholderError: true },
}

export const Empty: Story = {
  args: {
    children: (
      <tr>
        <td colSpan={3} className="text-center py-8 text-muted-foreground text-xs">No data</td>
      </tr>
    ),
  },
}

export const WithData: Story = {
  args: {
    tooltip: 'This table shows sample monitoring data.',
    onRefresh: async () => { await new Promise(r => setTimeout(r, 800)) },
    children: SAMPLE_ROWS,
  },
}

export const WithToolbar: Story = {
  args: {
    tooltip: 'Filter by status.',
    onRefresh: async () => { await new Promise(r => setTimeout(r, 800)) },
    toolbar: (
      <select className="text-xs border border-border rounded px-1 py-0.5 bg-background">
        <option value="all">All</option>
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </select>
    ),
    children: SAMPLE_ROWS,
  },
}

export const StickyHeaderScroll: Story = {
  args: {
    height: 150,
    tooltip: 'Scroll down to verify the header stays opaque.',
    children: Array.from({ length: 20 }, (_, i) => (
      <tr key={i} className="border-b border-border last:border-0 hover:bg-muted/30">
        <td className="px-2 py-1">Row {i + 1}</td>
        <td className="px-2 py-1 text-right tabular-nums">{i * 7}</td>
        <td className="px-2 py-1 text-muted-foreground">{i % 2 === 0 ? 'active' : 'inactive'}</td>
      </tr>
    )),
  },
}
