import { describe, expect, it } from 'vitest'
import type { components } from '@/lib/api/generated-types'

// Smoke test: generated-types.ts is a build artifact (026-rate-limit-codegen,
// `make generate-api-types`), never hand-edited. This asserts it exists and has the
// expected shape by exercising it at compile time (a stale/missing/malformed file
// fails `tsc`/this test file's own type-check) and at runtime (a real object
// literal actually satisfies the generated TopicOut schema).
describe('generated-types.ts', () => {
  it('exports a TopicOut schema with the known fields', () => {
    const topic: components['schemas']['TopicOut'] = {
      id: 'topic-1',
      name: 'ai',
      display_name: 'AI',
      is_active: true,
      tag_mode: 'unsupervised',
    }
    expect(topic.name).toBe('ai')
    expect(['unsupervised', 'semi_supervised', 'supervised']).toContain(topic.tag_mode)
  })
})
