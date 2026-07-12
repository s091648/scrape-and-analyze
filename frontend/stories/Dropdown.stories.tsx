import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { type ComponentProps, useState } from "react";
import { Globe } from "lucide-react";
import { Dropdown } from "../components/ui/dropdown";

const meta: Meta<typeof Dropdown> = {
  title: "UI/Dropdown",
  component: Dropdown,
  parameters: { layout: "centered" },
};

export default meta;
type Story = StoryObj<typeof Dropdown>;

function Controlled(args: ComponentProps<typeof Dropdown>) {
  const [value, setValue] = useState(args.value);
  return <Dropdown {...args} value={value} onChange={setValue} />;
}

export const Default: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    options: [
      { value: "alpha", label: "Alpha" },
      { value: "beta", label: "Beta" },
      { value: "gamma", label: "Gamma" },
    ],
    placeholder: "Select…",
  },
};

export const WithIconAndDots: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    icon: <Globe className="h-4 w-4 text-muted-foreground" />,
    value: "en",
    options: [
      { value: "en", label: "English", leadingDot: "#3b82f6" },
      { value: "zh-TW", label: "繁體中文", leadingDot: "#22c55e" },
      { value: "ja", label: "日本語", leadingDot: "#f97316" },
    ],
  },
};

export const WithGroups: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    placeholder: "Select a category…",
    groups: [
      {
        label: "Computer Science",
        options: [
          { value: "cs.AI", label: "Artificial Intelligence" },
          { value: "cs.LG", label: "Machine Learning" },
        ],
      },
      {
        label: "Physics",
        options: [
          { value: "physics.gen-ph", label: "General Physics" },
          { value: "quant-ph", label: "Quantum Physics" },
        ],
      },
    ],
  },
};

export const ManySearchable: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    placeholder: "Select…",
    searchable: true,
    searchPlaceholder: "Search…",
    options: Array.from({ length: 50 }, (_, i) => ({ value: `item-${i + 1}`, label: `Item ${i + 1}` })),
  },
};

export const Compact: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    size: "sm",
    value: "all",
    options: [
      { value: "all", label: "All" },
      { value: "local", label: "local" },
      { value: "production", label: "production" },
      { value: "test", label: "test" },
    ],
  },
};

export const WithDisabledOption: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    placeholder: "Select an icon…",
    options: [
      { value: "quote", label: "quote" },
      { value: "eye", label: "eye (used by another metric)", disabled: true },
      { value: "star", label: "star" },
    ],
  },
};
