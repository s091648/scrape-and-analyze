import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { type ComponentProps, useState } from "react";
import { DateFilter } from "../components/common/date-filter";

const meta: Meta<typeof DateFilter> = {
  title: "Common/DateFilter",
  component: DateFilter,
  parameters: { layout: "centered" },
};

export default meta;
type Story = StoryObj<typeof DateFilter>;

const labels = {
  any: "Any",
  after: "After",
  before: "Before",
  range: "Range",
  from: "From",
  to: "To",
};

function Controlled(args: ComponentProps<typeof DateFilter>) {
  const [after, setAfter] = useState(args.after);
  const [before, setBefore] = useState(args.before);
  return (
    <DateFilter
      {...args}
      after={after}
      before={before}
      onAfterChange={setAfter}
      onBeforeChange={setBefore}
    />
  );
}

export const Default: Story = {
  render: (args) => <Controlled {...args} />,
  args: { label: "Published", after: "", before: "", labels },
};

export const WithAfterDate: Story = {
  render: (args) => <Controlled {...args} />,
  args: { label: "Published", after: "2025-01-01", before: "", labels },
};

export const WithRange: Story = {
  render: (args) => <Controlled {...args} />,
  args: { label: "Scraped", after: "2025-01-01", before: "2025-03-31", labels },
};
