export interface Citation {
  index: number;
  file_name: string;
  page_start: number;
  page_end: number;
  section_title?: string | null;
  snippet: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  doc_id: string;
  file_name: string;
  page_start: number;
  page_end: number;
  section_title?: string | null;
  chunk_index: number;
  text: string;
  score: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources_start?: Citation[];
  citations?: Citation[];
  retrieved_chunks?: RetrievedChunk[];
  latency_ms?: number;
  model?: string;
  not_answerable?: boolean;
  isStreaming?: boolean;
}

export interface Thread {
  id: string;
  title?: string | null;
  summary?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface DocumentItem {
  id: string;
  file_name: string;
  hash: string;
  pages: number;
  chunk_count: number;
  indexed_at: string;
}

export interface MemoryItem {
  id: string;
  text: string;
  source_thread_id?: string | null;
  created_at: string;
}

export interface ChatSettings {
  top_k: number;
  use_reranking: boolean;
  user_id: string;
}
