import { v4 as uuid } from "uuid";

export function makeMockTagGroup(overrides: Record<string, unknown> = {}) {
  return {
    id: uuid(),
    name: "test_group",
    display_name: "Test Group",
    description: null,
    color_hex: "#6366f1",
    topic_id: uuid(),
    tags: [],
    similar_groups: [],
    ...overrides,
  };
}

export function makeMockTag(overrides: Record<string, unknown> = {}) {
  return {
    id: uuid(),
    name: "Test Tag",
    article_count: 3,
    ...overrides,
  };
}

export function makeMockSuggestion(overrides: Record<string, unknown> = {}) {
  return {
    id: uuid(),
    new_tag: makeMockTag({ name: "new tag" }),
    existing_tag: makeMockTag({ name: "existing tag" }),
    similarity_score: 0.92,
    article_id: uuid(),
    ...overrides,
  };
}

export function makeMockTagGroups(count: number) {
  return Array.from({ length: count }, (_, i) =>
    makeMockTagGroup({
      name: `group_${i}`,
      display_name: `Group ${i}`,
      tags: [
        makeMockTag({ name: `Tag ${i}-1`, article_count: 2 }),
        makeMockTag({ name: `Tag ${i}-2`, article_count: 5 }),
      ],
    })
  );
}
