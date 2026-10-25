import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bot,
  User,
  Copy,
  Check,
  AlertCircle,
  Clock,
  Cpu,
  FileCheck,
  Sparkles,
  HelpCircle,
  ShieldCheck,
  BookOpen,
} from 'lucide-react';
import { Citation, Message } from '../types';
import { SourcesPanel } from './SourcesPanel';

interface MessageItemProps {
  message: Message;
  onSelectCitation: (citation: Citation) => void;
  onConfirmFallback?: (approved: boolean) => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onSelectCitation,
  onConfirmFallback,
}) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Find citation by index
  const getCitationByIndex = (idx: number): Citation | undefined => {
    if (message.citations) {
      const match = message.citations.find((c) => c.index === idx);
      if (match) return match;
    }
    if (message.sources_start) {
      return message.sources_start.find((c) => c.index === idx);
    }
    return undefined;
  };

  // Custom component for inline markdown text to render [n] as clickable chips
  const renderFormattedContent = (content: string) => {
    const parts = content.split(/(\[\d+\])/g);
    return parts.map((part, index) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const idx = parseInt(match[1], 10);
        const cite = getCitationByIndex(idx);
        return (
          <button
            key={`chip-${index}`}
            onClick={() => {
              if (cite) {
                onSelectCitation(cite);
              }
            }}
            title={cite ? `${cite.file_name} (p. ${cite.page_start})` : `Source [${idx}]`}
            className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded bg-emerald-100 hover:bg-emerald-200 dark:bg-emerald-950/80 dark:hover:bg-emerald-900 text-emerald-700 dark:text-emerald-300 transition-colors shadow-sm cursor-pointer select-none align-baseline border border-emerald-300 dark:border-emerald-800"
          >
            [{idx}]
          </button>
        );
      }
      return <span key={`text-${index}`}>{part}</span>;
    });
  };

  // Render badge based on answer source
  const renderSourceBadge = () => {
    if (isUser || !message.answer_source) return null;

    switch (message.answer_source) {
      case 'knowledge_base':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <BookOpen className="w-3 h-3" />
            <span>Document Grounded</span>
          </span>
        );
      case 'partial_document':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <Sparkles className="w-3 h-3" />
            <span>Partially Grounded</span>
          </span>
        );
      case 'general_ai':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
            <Sparkles className="w-3 h-3" />
            <span>General AI Knowledge</span>
          </span>
        );
      case 'insufficient_info':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
            <AlertCircle className="w-3 h-3" />
            <span>Not in Documents</span>
          </span>
        );
      case 'pending_fallback':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-violet-100 dark:bg-violet-950/60 text-violet-700 dark:text-violet-300 border border-violet-200 dark:border-violet-800">
            <HelpCircle className="w-3 h-3" />
            <span>Action Required</span>
          </span>
        );
      default:
        return null;
    }
  };

  const isPendingFallback = message.answer_source === 'pending_fallback' || !!message.fallback_prompt;

  return (
    <div
      className={`py-6 px-4 md:px-6 transition-colors ${
        isUser
          ? 'bg-transparent'
          : 'bg-white dark:bg-gray-900/40 border-y border-gray-100 dark:border-gray-800/60'
      }`}
    >
      <div className="max-w-3xl mx-auto flex gap-4 items-start">
        {/* Avatar */}
        <div
          className={`shrink-0 w-8 h-8 rounded-xl flex items-center justify-center font-medium text-sm shadow-sm ${
            isUser
              ? 'bg-gradient-to-tr from-gray-700 to-gray-900 text-white dark:from-gray-600 dark:to-gray-700'
              : 'bg-gradient-to-tr from-emerald-500 to-teal-600 text-white'
          }`}
        >
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-xs text-gray-500 dark:text-gray-400 tracking-wide uppercase">
                {isUser ? 'You' : 'DocuRAG Assistant'}
              </span>
              {renderSourceBadge()}
            </div>

            {!isUser && !message.isStreaming && message.content && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
                title="Copy response"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            )}
          </div>

          {/* Assistant: Sources Used (START panel - only when grounded in documents) */}
          {!isUser && message.sources_start && message.sources_start.length > 0 && message.answer_source !== 'general_ai' && (
            <SourcesPanel sources={message.sources_start} onSelectCitation={onSelectCitation} />
          )}

          {/* General AI Notice Banner */}
          {!isUser && message.answer_source === 'general_ai' && (
            <div className="mb-3 p-3 rounded-xl bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200/80 dark:border-indigo-800/60 flex items-start gap-2.5 text-xs text-indigo-900 dark:text-indigo-200 shadow-sm">
              <Sparkles className="w-4 h-4 shrink-0 text-indigo-600 dark:text-indigo-400 mt-0.5" />
              <div>
                <strong>Notice:</strong> This response is generated from <strong>general AI parametric knowledge</strong> because sufficient evidence was not found in your uploaded documents.
              </div>
            </div>
          )}

          {/* Unanswerable banner (when not already displaying fallback prompt) */}
          {!isUser && message.not_answerable && !isPendingFallback && message.answer_source !== 'general_ai' && (
            <div className="mb-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 flex items-center gap-2.5 text-xs text-amber-800 dark:text-amber-200">
              <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span>
                <strong>Document Grounding Notice:</strong> This question could not be verified in the ingested PDF corpus.
              </span>
            </div>
          )}

          {/* Main message body */}
          <div className="text-gray-800 dark:text-gray-200 text-sm leading-relaxed break-words">
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className={`prose dark:prose-invert max-w-none prose-p:my-2 prose-pre:my-3 ${message.isStreaming ? 'streaming-cursor' : ''}`}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => {
                      if (typeof children === 'string') {
                        return <p>{renderFormattedContent(children)}</p>;
                      }
                      return <p>{children}</p>;
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {/* Ask Before Fallback Action Prompt */}
          {!isUser && !message.isStreaming && isPendingFallback && onConfirmFallback && (
            <div className="mt-3.5 p-3.5 rounded-xl bg-violet-50/80 dark:bg-violet-950/40 border border-violet-200 dark:border-violet-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
              <div className="flex items-center gap-2 text-xs text-violet-900 dark:text-violet-200">
                <HelpCircle className="w-4 h-4 text-violet-600 dark:text-violet-400 shrink-0" />
                <span>Would you like to generate this answer from general AI knowledge?</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => onConfirmFallback(true)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition shadow-sm flex items-center gap-1.5 cursor-pointer"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Yes, Answer with AI</span>
                </button>
                <button
                  type="button"
                  onClick={() => onConfirmFallback(false)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-200 hover:bg-gray-300 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 transition cursor-pointer"
                >
                  <span>No, Keep Strict</span>
                </button>
              </div>
            </div>
          )}

          {/* Assistant: Citations List (END footer) */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-800">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2">
                <FileCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>Verified Citations ({message.citations.length})</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {message.citations.map((c) => (
                  <button
                    key={`cite-footer-${c.index}`}
                    onClick={() => onSelectCitation(c)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 transition"
                  >
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">[{c.index}]</span>
                    <span className="truncate max-w-[150px]">{c.file_name}</span>
                    <span className="text-gray-400">p.{c.page_start}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Assistant metadata badges */}
          {!isUser && !message.isStreaming && (message.latency_ms || message.model) && (
            <div className="mt-3 flex items-center gap-3 text-[11px] text-gray-400">
              {message.latency_ms && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {message.latency_ms} ms
                </span>
              )}
              {message.model && (
                <span className="flex items-center gap-1">
                  <Cpu className="w-3 h-3" />
                  {message.model}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
