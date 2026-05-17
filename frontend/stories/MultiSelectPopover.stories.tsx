import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { type ComponentProps, useState } from "react";
import { MultiSelectPopover } from "../components/common/multi-select-popover";

const meta: Meta<typeof MultiSelectPopover> = {
  title: "Common/MultiSelectPopover",
  component: MultiSelectPopover,
  parameters: { layout: "centered" },
};

export default meta;
type Story = StoryObj<typeof MultiSelectPopover>;

function Controlled(args: ComponentProps<typeof MultiSelectPopover>) {
  const [selected, setSelected] = useState(args.selected);
  return <MultiSelectPopover {...args} selected={selected} onChange={setSelected} />;
}

export const Default: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    label: "Source",
    options: ["arxiv", "rss", "blog", "hackernews"],
    selected: [],
    searchPlaceholder: "Search sources…",
  },
};

export const WithPreselected: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    label: "Tags",
    options: ["AI", "Machine Learning", "Robotics", "Systems", "Security", "Networking"],
    selected: ["AI", "Robotics"],
  },
};

export const ManyOptions: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    label: "Category",
    options: Array.from({ length: 20 }, (_, i) => `Category ${i + 1}`),
    selected: [],
  },
};
