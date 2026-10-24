import { useState, useEffect, useRef } from 'react';
import { Citation, Message, Thread, ChatSettings } from '../types';
import {
  createThread,
  deleteThread as apiDeleteThread,
  fetchThread,
  fetchThreads,
  streamChat,
  updateThread as apiUpdateThread,
} from '../api/client';

export function useChat() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load threads on mount
  const loadThreads = async () => {
    try {
      const list = await fetchThreads();
      setThreads(list);
    } catch (e) {
      console.error('Failed to load threads', e);
    }
  };

  useEffect(() => {
    loadThreads();
  }, []);

  // When active thread changes, load its messages
  const selectThread = async (threadId: string) => {
    setActiveThreadId(threadId);
    try {
      const data = await fetchThread(threadId);
      setMessages(data.messages || []);
    } catch (e) {
      console.error('Failed to load thread messages', e);
      setMessages([]);
    }
  };

  const startNewChat = () => {
    setActiveThreadId(null);
    setMessages([]);
  };

  const renameThread = async (threadId: string, newTitle: string) => {
    try {
      await apiUpdateThread(threadId, newTitle);
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? { ...t, title: newTitle } : t))
      );
    } catch (e) {
      console.error('Failed to rename thread', e);
    }
  };

  const deleteThread = async (threadId: string) => {
    try {
      await apiDeleteThread(threadId);
      setThreads((prev) => prev.filter((t) => t.id !== threadId));
      if (activeThreadId === threadId) {
        startNewChat();
      }
    } catch (e) {
      console.error('Failed to delete thread', e);
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m))
    );
  };

  const sendMessage = async (text: string, settings: ChatSettings) => {
    if (isStreaming) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    };

    const assistantPlaceholder: Message = {
      id: `asst-${Date.now()}`,
      role: 'assistant',
      content: '',
      isStreaming: true,
      sources_start: [],
      citations: [],
    };

    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamChat(
        text,
        activeThreadId,
        settings,
        {
          onSourcesStart: (sources: Citation[]) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholder.id
                  ? { ...m, sources_start: sources }
                  : m
              )
            );
          },
          onToken: (token: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholder.id
                  ? { ...m, content: m.content + token }
                  : m
              )
            );
          },
          onSourcesEnd: (sources: Citation[]) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholder.id
                  ? { ...m, citations: sources }
                  : m
              )
            );
          },
          onDone: (data) => {
            setIsStreaming(false);
            abortControllerRef.current = null;

            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholder.id
                  ? {
                      ...m,
                      id: data.message_id,
                      latency_ms: data.latency_ms,
                      model: data.model,
                      not_answerable: data.not_answerable,
                      isStreaming: false,
                    }
                  : m
              )
            );

            // If this was a new thread, update activeThreadId and reload threads list
            if (!activeThreadId && data.thread_id) {
              setActiveThreadId(data.thread_id);
              loadThreads();
            }
          },
          onError: (err: string) => {
            setIsStreaming(false);
            abortControllerRef.current = null;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholder.id
                  ? {
                      ...m,
                      content: m.content || `⚠️ Error: ${err}`,
                      isStreaming: false,
                    }
                  : m
              )
            );
          },
        },
        controller.signal
      );
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted by user');
      } else {
        console.error('Chat error', err);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantPlaceholder.id
              ? {
                  ...m,
                  content: m.content || `⚠️ Error: ${err.message || 'Stream connection failed'}`,
                  isStreaming: false,
                }
              : m
          )
        );
      }
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  return {
    threads,
    activeThreadId,
    messages,
    isStreaming,
    selectThread,
    startNewChat,
    renameThread,
    deleteThread,
    sendMessage,
    stopStreaming,
  };
}
