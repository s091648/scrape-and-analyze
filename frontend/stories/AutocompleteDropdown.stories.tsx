import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Command } from "../components/ui/command";
import { AutocompleteDropdown } from "../components/features/articles/autocomplete-dropdown";

// cmdk's CommandList/CommandItem require a <Command> ancestor for context — wrapped here
// purely for Storybook rendering; in the real app that's SearchBar (see search-bar.tsx).
const meta: Meta<typeof AutocompleteDropdown> = {
  title: "Features/Articles/AutocompleteDropdown",
  component: AutocompleteDropdown,
  parameters: { layout: "padded" },
  decorators: [
    (Story) => (
      <Command shouldFilter={false} className="rounded-md border border-border">
        <Story />
      </Command>
    ),
  ],
  args: {
    suggestions: [],
    onSelect: () => {},
    query: "",
  },
};

export default meta;
type Story = StoryObj<typeof AutocompleteDropdown>;

export const Empty: Story = {};

// The tokenizer (src/modules/search/domain/services/tokenizer.py) splits English text on
// every non-alphanumeric character, including spaces — a suggestion is always a single
// word, never a multi-word phrase. These examples are deliberately single words so
// Storybook doesn't misrepresent what the real index can ever produce.
export const Populated: Story = {
  args: {
    suggestions: [
      { term: "learning", occurrence_count: 42 },
      { term: "language", occurrence_count: 18 },
      { term: "model", occurrence_count: 9 },
    ],
    query: "l",
  },
};

export const SingleSuggestion: Story = {
  args: {
    suggestions: [{ term: "learning", occurrence_count: 5 }],
    query: "l",
  },
};

// Contains-anywhere matching (research.md's suffix-expansion decision) — "arn" isn't a
// prefix of "learning", it occurs in the middle, and the highlight lands there too.
export const HighlightsMatchAnywhereInTerm: Story = {
  args: {
    suggestions: [{ term: "learning", occurrence_count: 42 }],
    query: "arn",
  },
};
