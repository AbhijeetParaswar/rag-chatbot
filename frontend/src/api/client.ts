import { AnswerMode, Citation, DocumentItem, MemoryItem, Message, Thread } from '../types';

const API_BASE = '/api';

export async function fetchThreads(userId: string = 'default'): Promise<Thread[]> {
  const res = await fetch(`${API_BASE}/threads?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error('Failed to load threads');
  return res.json();
}

export async function fetchThread(threadId: string): Promise<Thread & { messages: Message[] }> {
  const res = await fetch(`${API_BASE}/threads/${encodeURIComponent(threadId)}`);
  if (!res.ok) throw new Error('Failed to load thread details');
  return res.json();
}

export async function createThread(userId: string = 'default', title?: string): Promise<Thread> {
  const res = await fetch(`${API_BASE}/threads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, title }),
  });
  if (!res.ok) throw new Error('Failed to create thread');
  return res.json();
}

export async function updateThread(threadId: string, title: string): Promise<Thread> {
  const res = await fetch(`${API_BASE}/threads/${encodeURIComponent(threadId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to rename thread');
  return res.json();
}

export async function deleteThread(threadId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/threads/${encodeURIComponent(threadId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete thread');
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) throw new Error('Failed to fetch indexed documents');
  return res.json();
}

export async function uploadDocument(file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function syncDocuments(): Promise<any> {
  const res = await fetch(`${API_BASE}/documents/sync`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to sync documents from disk');
  return res.json();
}

export async function fetchMemories(userId: string = 'default'): Promise<MemoryItem[]> {
  const res = await fetch(`${API_BASE}/memory?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error('Failed to fetch memories');
  return res.json();
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(memoryId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete memory');
}

export interface StreamCallbacks {
  onSourcesStart: (sources: Citation[]) => void;
  onToken: (token: string) => void;
  onSourcesEnd: (sources: Citation[]) => void;
  onDone: (data: {
    message_id: string;
    thread_id: string;
    thread_title?: string | null;
    latency_ms: number;
    model: string;
    not_answerable: boolean;
    evidence_status?: string | null;
    answer_source?: string | null;
    fallback_prompt?: string | null;
  }) => void;
  onError: (err: string) => void;
}

export async function streamChat(
  query: string,
  threadId: string | null,
  settings: { top_k: number; use_reranking: boolean; user_id: string; answer_mode: AnswerMode },
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
  docFilter?: string[],
  fallbackApproved?: boolean | null,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      thread_id: threadId,
      user_id: settings.user_id,
      top_k: settings.top_k,
      use_reranking: settings.use_reranking,
      answer_mode: settings.answer_mode,
      doc_filter: docFilter && docFilter.length > 0 ? docFilter : undefined,
      fallback_approved: fallbackApproved !== undefined ? fallbackApproved : undefined,
    }),
    signal,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Server returned ${res.status}: ${err}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('ReadableStream not supported');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent = '';
    let currentData = '';

    for (const rawLine of lines) {
      const line = rawLine.replace(/\r$/, '');
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        currentData = line.slice(5).trim();
      } else if (line === '') {
        if (currentEvent && currentData) {
          try {
            const parsed = JSON.parse(currentData);
            if (currentEvent === 'sources_start') {
              callbacks.onSourcesStart(parsed.sources || []);
            } else if (currentEvent === 'token') {
              callbacks.onToken(parsed.token || '');
            } else if (currentEvent === 'sources_end') {
              callbacks.onSourcesEnd(parsed.sources || []);
            } else if (currentEvent === 'done') {
              callbacks.onDone(parsed);
            } else if (currentEvent === 'error') {
              callbacks.onError(parsed.error || 'Unknown error');
            }
          } catch (e) {
            console.error('Failed to parse SSE event data', e, currentData);
          }
        }
        currentEvent = '';
        currentData = '';
      }
    }
  }
}
