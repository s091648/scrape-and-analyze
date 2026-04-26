'use client'
import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { apiFetch } from '@/lib/api-fetch'

export interface Topic {
  id: string
  name: string
  display_name: string
  color_hex: string | null
  sort_order: number | null
}

interface TopicContextValue {
  topics: Topic[]
  selectedTopicId: string | null
  selectedTopic: Topic | null
  setSelectedTopicId: (id: string) => void
  refresh: () => Promise<void>
  isLoading: boolean
}

const TopicContext = createContext<TopicContextValue>({
  topics: [],
  selectedTopicId: null,
  selectedTopic: null,
  setSelectedTopicId: () => {},
  refresh: async () => {},
  isLoading: true,
})

const STORAGE_KEY = 'selectedTopicId'

export function TopicProvider({ children }: { children: ReactNode }) {
  const [topics, setTopics] = useState<Topic[]>([])
  const [selectedTopicId, setSelectedTopicIdState] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  async function fetchTopics() {
    const raw = await apiFetch('/topics').then(r => r.json())
    const data: Topic[] = Array.isArray(raw) ? raw : []
    setTopics(data)
    const stored = localStorage.getItem(STORAGE_KEY)
    const valid = data.find(t => t.id === stored)
    const initial = valid ? stored : (data[0]?.id ?? null)
    setSelectedTopicIdState(prev => {
      // Keep current selection if it still exists in the new list
      if (prev && data.find(t => t.id === prev)) return prev
      if (initial) localStorage.setItem(STORAGE_KEY, initial)
      return initial
    })
  }

  useEffect(() => {
    setIsLoading(true)
    fetchTopics().finally(() => setIsLoading(false))
  }, [])

  function setSelectedTopicId(id: string) {
    setSelectedTopicIdState(id)
    localStorage.setItem(STORAGE_KEY, id)
  }

  async function refresh() {
    await fetchTopics()
  }

  const selectedTopic = topics.find(t => t.id === selectedTopicId) ?? null

  return (
    <TopicContext.Provider value={{ topics, selectedTopicId, selectedTopic, setSelectedTopicId, refresh, isLoading }}>
      {children}
    </TopicContext.Provider>
  )
}

export function useTopic() {
  return useContext(TopicContext)
}
