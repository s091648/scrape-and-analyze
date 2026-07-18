import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { ToggleRow } from '../components/ui/toggle-row'

const meta: Meta<typeof ToggleRow> = {
  title: 'UI/ToggleRow',
  component: ToggleRow,
  parameters: { layout: 'padded' },
}
export default meta
type Story = StoryObj<typeof ToggleRow>

export const Checked: Story = {
  render: () => {
    const [checked, setChecked] = useState(true)
    return (
      <div className="max-w-sm">
        <ToggleRow label="Email notifications" checked={checked} onCheckedChange={setChecked} />
      </div>
    )
  },
}

export const Unchecked: Story = {
  render: () => {
    const [checked, setChecked] = useState(false)
    return (
      <div className="max-w-sm">
        <ToggleRow label="Telegram notifications" checked={checked} onCheckedChange={setChecked} />
      </div>
    )
  },
}

export const WithDescription: Story = {
  render: () => {
    const [checked, setChecked] = useState(true)
    return (
      <div className="max-w-sm">
        <ToggleRow
          label="Telegram notifications"
          description="Requires a Telegram Chat ID to be set below."
          checked={checked}
          onCheckedChange={setChecked}
        />
      </div>
    )
  },
}

export const Disabled: Story = {
  render: () => (
    <div className="max-w-sm">
      <ToggleRow label="Email notifications" checked={false} onCheckedChange={() => {}} disabled />
    </div>
  ),
}

export const WithColorDotAndDescription: Story = {
  render: () => {
    const [checked, setChecked] = useState(true)
    return (
      <div className="max-w-sm">
        <ToggleRow
          label={
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full border border-border" style={{ backgroundColor: '#3b82f6' }} />
              AI Research
            </span>
          }
          description="Weekly summaries of the top papers and articles in this topic."
          checked={checked}
          onCheckedChange={setChecked}
        />
      </div>
    )
  },
}
