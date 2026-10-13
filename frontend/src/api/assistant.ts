import { apiClient } from '@/api/client'

export interface ConversationSummary {
  id: string
  title: string | null
  updated_at: string
  equipment_id: string | null
  status: string
}

export interface CitationSource {
  id: string
  type?: 'document' | 'work_order'
  title: string
  filename?: string
  source_path?: string
  chapter?: string | null
  page_start?: number | null
  page_end?: number | null
  excerpt: string
  description?: string
  resolution?: string
}

export interface ConversationMessage {
  id: string
  role: 'assistant' | 'user'
  content: string
  sources?: CitationSource[]
}

export interface ConversationHistory {
  conversation_id: string
  equipment_id: string | null
  equipment_selector: string | null
  messages: ConversationMessage[]
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const { data } = await apiClient.get<ConversationSummary[]>('/api/v1/assistant/conversations')
  return data
}

export async function getConversation(conversationId: string): Promise<ConversationHistory> {
  const { data } = await apiClient.get<ConversationHistory>(`/api/v1/assistant/conversations/${conversationId}`)
  return data
}
