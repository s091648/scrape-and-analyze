import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { AccordionSection } from "../components/ui/accordion-section";

const meta: Meta<typeof AccordionSection> = {
  title: "UI/AccordionSection",
  component: AccordionSection,
  parameters: { layout: "padded" },
};

export default meta;
type Story = StoryObj<typeof AccordionSection>;

const PlaceholderCard = ({ label }: { label: string }) => (
  <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
    {label}
  </div>
);

export const DefaultOpen: Story = {
  render: () => (
    <div className="max-w-lg">
      <AccordionSection title="LLM" badge={2}>
        <PlaceholderCard label="gemini-2.5-flash" />
        <PlaceholderCard label="claude-sonnet-4-5" />
      </AccordionSection>
    </div>
  ),
};

export const DefaultClosed: Story = {
  render: () => (
    <div className="max-w-lg">
      <AccordionSection title="Embedding" badge={1} defaultOpen={false}>
        <PlaceholderCard label="text-embedding-3-small" />
      </AccordionSection>
    </div>
  ),
};

export const NoBadge: Story = {
  render: () => (
    <div className="max-w-lg">
      <AccordionSection title="Empty Section">
        <p className="text-sm text-muted-foreground text-center py-4">No items yet.</p>
      </AccordionSection>
    </div>
  ),
};

export const MultipleSections: Story = {
  render: () => (
    <div className="max-w-lg space-y-4">
      <AccordionSection title="LLM" badge={3}>
        <PlaceholderCard label="gemini-2.5-flash · p1" />
        <PlaceholderCard label="claude-sonnet-4-5 · p2" />
        <PlaceholderCard label="gpt-4o · p3" />
      </AccordionSection>
      <AccordionSection title="Embedding" badge={1}>
        <PlaceholderCard label="text-embedding-3-small · p1" />
      </AccordionSection>
    </div>
  ),
};
