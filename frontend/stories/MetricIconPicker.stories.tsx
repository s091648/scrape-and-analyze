import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { type ComponentProps, useState } from 'react'
import { MetricIconPicker } from '../components/features/articles/metric-icon-picker'

const meta: Meta<typeof MetricIconPicker> = {
  title: 'Features/Articles/MetricIconPicker',
  component: MetricIconPicker,
  parameters: { layout: 'centered' },
}
export default meta
type Story = StoryObj<typeof MetricIconPicker>

function Controlled(args: ComponentProps<typeof MetricIconPicker>) {
  const [value, setValue] = useState(args.value)
  return <MetricIconPicker {...args} value={value} onChange={setValue} />
}

export const Default: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    value: null,
    disabledIcons: new Map(),
    ariaLabel: 'citation_count icon',
  },
}

export const WithCurrentSelection: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    value: 'trophy',
    disabledIcons: new Map(),
    ariaLabel: 'citation_count icon',
  },
}

export const WithIconsUsedByOtherMetrics: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    value: 'trophy',
    disabledIcons: new Map([
      ['quote', 'Citation Count'],
      ['eye', 'View Count'],
      ['star', 'Impact Factor'],
    ]),
    ariaLabel: 'citation_count icon',
  },
}
