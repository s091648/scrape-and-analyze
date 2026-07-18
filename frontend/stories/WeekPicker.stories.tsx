import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { WeekPicker } from '../components/ui/week-picker'

const meta: Meta<typeof WeekPicker> = {
  title: 'UI/WeekPicker',
  component: WeekPicker,
  parameters: { layout: 'centered' },
}
export default meta
type Story = StoryObj<typeof WeekPicker>

export const NoSelection: Story = {
  render: () => {
    const [value, setValue] = useState<Date | null>(null)
    return <WeekPicker value={value} onSelectWeek={setValue} />
  },
}

export const WithSelection: Story = {
  render: () => {
    const [value, setValue] = useState<Date | null>(new Date(2026, 5, 15))
    return <WeekPicker value={value} onSelectWeek={setValue} />
  },
}

export const ChineseLocale: Story = {
  render: () => {
    const [value, setValue] = useState<Date | null>(new Date(2026, 5, 15))
    return <WeekPicker value={value} onSelectWeek={setValue} locale="zh-TW" />
  },
}

export const WithDateBounds: Story = {
  render: () => {
    const [value, setValue] = useState<Date | null>(new Date(2026, 5, 8))
    return (
      <WeekPicker
        value={value}
        onSelectWeek={setValue}
        minDate={new Date(2026, 4, 1)}
        maxDate={new Date(2026, 5, 30)}
      />
    )
  },
}

export const Compact: Story = {
  render: () => {
    const [value, setValue] = useState<Date | null>(new Date(2026, 5, 15))
    return <WeekPicker value={value} onSelectWeek={setValue} compact />
  },
}

export const OnlySomeWeeksAvailable: Story = {
  render: () => {
    const [value, setValue] = useState<Date | null>(new Date(2026, 5, 15))
    const availableMondays = new Set(['2026-06-01', '2026-06-08', '2026-06-15'])
    return (
      <WeekPicker
        value={value}
        onSelectWeek={setValue}
        isWeekAvailable={monday => availableMondays.has(monday.toISOString().slice(0, 10))}
      />
    )
  },
}
