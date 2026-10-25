import { useState, useEffect, useRef } from 'react';
import { AnswerMode, Citation, Message, Thread, ChatSettings } from '../types';
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

  // Linear typing queue refs for ChatGPT-like smooth streaming
  const incomingBufferRef = useRef<string>('');
  const displayedTextRef = useRef<string>('');
  const typingTimerRef = useRef<number | null>(null);
  const donePayloadRef = useRef<any>(null);
  const currentMsgIdRef = useRef<string>('');

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
    return () => {
      if (typingTimerRef.current) {
        clearTimeout(typingTimerRef.current);
      }
    };
  }, []);

  // When active thread changes, load its messages
  const selectThread = async (threadId: string) => {
    if (typingTimerRef.current) {
      clearTimeout(typingTimerRef.current);
      typingTimerRef.current = null;
    }
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
    if (typingTimerRef.current) {
      clearTimeout(typingTimerRef.current);
      typingTimerRef.current = null;
    }
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
    if (typingTimerRef.current) {
      clearTimeout(typingTimerRef.current);
      typingTimerRef.current = null;
    }
    // Flush remaining buffer immediately
    if (incomingBufferRef.current.length > 0) {
      displayedTextRef.current += incomingBufferRef.current;
      incomingBufferRef.current = '';
    }
    const targetId = currentMsgIdRef.current;
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === targetId || m.isStreaming
          ? { ...m, content: displayedTextRef.current || m.content, isStreaming: false }
          : m
      )
    );
  };

  // Linear typing loop that animates tokens smoothly like ChatGPT
  const startLinearTyping = () => {
    if (typingTimerRef.current) return;

    const tick = () => {
      const buffer = incomingBufferRef.current;
      const targetId = currentMsgIdRef.current;

      if (buffer.length > 0) {
        // Dynamically pace step size so it's smooth at normal speed, but catches up if buffer is large
        let stepSize = 1;
        if (buffer.length > 120) {
          stepSize = 6;
        } else if (buffer.length > 60) {
          stepSize = 3;
        } else if (buffer.length > 20) {
          stepSize = 2;
        } else {
          stepSize = 1;
        }

        const nextSlice = buffer.slice(0, stepSize);
        incomingBufferRef.current = buffer.slice(stepSize);
        displayedTextRef.current += nextSlice;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === targetId ? { ...m, content: displayedTextRef.current } : m
          )
        );

        // Schedule next tick (~16-18ms gives silky ~60fps linear output)
        typingTimerRef.current = window.setTimeout(tick, 18);
      } else {
        // Buffer is empty - check if stream has finished
        if (donePayloadRef.current !== null) {
          const data = donePayloadRef.current;
          donePayloadRef.current = null;
          if (typingTimerRef.current) {
            clearTimeout(typingTimerRef.current);
            typingTimerRef.current = null;
          }

          setIsStreaming(false);
          abortControllerRef.current = null;

          setMessages((prev) =>
            prev.map((m) =>
              m.id === targetId
                ? {
                    ...m,
                    id: data.message_id || m.id,
                    content: displayedTextRef.current,
                    latency_ms: data.latency_ms,
                    model: data.model,
                    not_answerable: data.not_answerable,
                    evidence_status: data.evidence_status as any,
                    answer_source: data.answer_source as any,
                    fallback_prompt: data.fallback_prompt || null,
                    isStreaming: false,
                  }
                : m
            )
          );

          if (!activeThreadId && data.thread_id) {
            setActiveThreadId(data.thread_id);
          }

          if (data.thread_title && data.thread_id) {
            setThreads((prev) =>
              prev.map((t) =>
                t.id === data.thread_id ? { ...t, title: data.thread_title } : t
              )
            );
          }

          loadThreads();
        } else {
          // Buffer is empty but stream still active from server; poll again
          typingTimerRef.current = window.setTimeout(tick, 20);
        }
      }
    };

    typingTimerRef.current = window.setTimeout(tick, 18);
  };

  const sendMessage = async (
    text: string,
    settings: ChatSettings,
    docFilter?: string[],
    fallbackApproved?: boolean | null,
  ) => {
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

    // Reset streaming state and buffers
    incomingBufferRef.current = '';
    displayedTextRef.current = '';
    donePayloadRef.current = null;
    currentMsgIdRef.current = assistantPlaceholder.id;
    if (typingTimerRef.current) {
      clearTimeout(typingTimerRef.current);
      typingTimerRef.current = null;
    }

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
                m.id === currentMsgIdRef.current
                  ? { ...m, sources_start: sources }
                  : m
              )
            );
          },
          onToken: (token: string) => {
            // Append token to incoming queue and ensure linear typewriter is active
            incomingBufferRef.current += token;
            if (!typingTimerRef.current) {
              startLinearTyping();
            }
          },
          onSourcesEnd: (sources: Citation[]) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentMsgIdRef.current
                  ? { ...m, citations: sources }
                  : m
              )
            );
          },
          onDone: (data) => {
            // Store done payload - linear typing loop will drain any remaining buffer and finalize smoothly
            donePayloadRef.current = data;
            if (!typingTimerRef.current) {
              startLinearTyping();
            }
          },
          onError: (err: string) => {
            if (typingTimerRef.current) {
              clearTimeout(typingTimerRef.current);
              typingTimerRef.current = null;
            }
            setIsStreaming(false);
            abortControllerRef.current = null;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentMsgIdRef.current
                  ? {
                      ...m,
                      content: displayedTextRef.current || m.content || `⚠️ Error: ${err}`,
                      isStreaming: false,
                    }
                  : m
              )
            );
          },
        },
        controller.signal,
        docFilter,
        fallbackApproved,
      );
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted by user');
      } else {
        console.error('Chat error', err);
        if (typingTimerRef.current) {
          clearTimeout(typingTimerRef.current);
          typingTimerRef.current = null;
        }
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === currentMsgIdRef.current
              ? {
                  ...m,
                  content: displayedTextRef.current || m.content || `⚠️ Error: ${err.message || 'Stream connection failed'}`,
                  isStreaming: false,
                }
              : m
          )
        );
      }
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
