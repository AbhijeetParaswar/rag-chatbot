import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, Sparkles, BookOpen, ShieldAlert, Cpu } from 'lucide-react';
import { Citation, Message } from '../types';
import { MessageItem } from './MessageItem';

interface ChatAreaProps {
  messages: Message[];
  isStreaming: boolean;
  onSendMessage: (text: string) => void;
  onStopStreaming: () => void;
  onSelectCitation: (citation: Citation) => void;
  activeThreadTitle?: string | null;
}

const STARTER_PROMPTS = [
  {
    icon: BookOpen,
    title: 'Syllabus & Grading',
    prompt: 'What is the grading breakdown and late submission policy in the CS101 syllabus?',
  },
  {
    icon: ShieldAlert,
    title: 'Academic Policy',
    prompt: 'What constitutes plagiarism and what are the student appeal procedures in the university policy?',
  },
  {
    icon: Cpu,
    title: 'Transformer Research',
    prompt: 'How does Scaled Dot-Product and Multi-Head Attention work in transformer architectures?',
  },
];

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isStreaming,
  onSendMessage,
  onStopStreaming,
  onSelectCitation,
  activeThreadTitle,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    onSendMessage(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputResize = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-white dark:bg-gray-950 relative">
      {/* Top Navbar */}
      <header className="h-14 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-6 bg-white/70 dark:bg-gray-950/70 backdrop-blur-md shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <h2 className="font-semibold text-sm text-gray-800 dark:text-gray-200 truncate max-w-md">
            {activeThreadTitle || 'New Conversation'}
          </h2>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span className="hidden sm:inline font-mono text-[11px] px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
            BAAI/bge-small • ChromaDB
          </span>
        </div>
      </header>

      {/* Messages Scroll View */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-600 flex items-center justify-center text-white shadow-lg mb-4">
              <Sparkles className="w-7 h-7" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              How can I help with your documents today?
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-8 max-w-md">
              Ask questions grounded strictly in your PDFs. Responses include verified source citations, exact page
              numbers, and zero hallucinations.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
              {STARTER_PROMPTS.map((starter, idx) => {
                const Icon = starter.icon;
                return (
                  <button
                    key={idx}
                    onClick={() => onSendMessage(starter.prompt)}
                    className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/40 hover:bg-emerald-50/50 dark:hover:bg-emerald-950/20 hover:border-emerald-500/40 transition text-left group flex flex-col justify-between"
                  >
                    <div>
                      <Icon className="w-5 h-5 text-emerald-600 dark:text-emerald-400 mb-2" />
                      <div className="font-semibold text-xs text-gray-800 dark:text-gray-200 mb-1">{starter.title}</div>
                      <p className="text-[11px] text-gray-500 dark:text-gray-400 line-clamp-3 leading-relaxed">
                        {starter.prompt}
                      </p>
                    </div>
                    <div className="mt-3 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 opacity-0 group-hover:opacity-100 transition">
                      Ask this →
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="pb-8">
            {messages.map((m) => (
              <MessageItem key={m.id} message={m} onSelectCitation={onSelectCitation} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Input Area */}
      <div className="p-4 bg-white/80 dark:bg-gray-950/80 backdrop-blur-md border-t border-gray-200 dark:border-gray-800 shrink-0">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end rounded-2xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm focus-within:border-emerald-500 focus-within:ring-1 focus-within:ring-emerald-500 transition overflow-hidden">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={handleInputResize}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your documents... (Shift+Enter for newline)"
              className="w-full resize-none max-h-40 py-3.5 pl-4 pr-14 text-sm bg-transparent text-gray-900 dark:text-gray-100 focus:outline-none placeholder-gray-400"
            />

            <div className="absolute right-2.5 bottom-2.5">
              {isStreaming ? (
                <button
                  onClick={onStopStreaming}
                  className="p-2 rounded-xl bg-red-600 hover:bg-red-700 text-white transition shadow-sm"
                  title="Stop generating"
                >
                  <Square className="w-4 h-4 fill-white" />
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="p-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white transition shadow-sm"
                  title="Send message"
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          <p className="mt-2 text-center text-[11px] text-gray-400 dark:text-gray-500">
            Answers are strictly grounded in ingested PDFs. Verified source markers [n] are clickable.
          </p>
        </div>
      </div>
    </div>
  );
};
