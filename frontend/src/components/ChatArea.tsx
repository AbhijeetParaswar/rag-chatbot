import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Square,
  Sparkles,
  BookOpen,
  ShieldAlert,
  Cpu,
  Paperclip,
  FileText,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  FileUp,
} from 'lucide-react';
import { Citation, Message } from '../types';
import { MessageItem } from './MessageItem';
import { uploadDocument } from '../api/client';

interface AttachedFile {
  name: string;
  size?: number;
  status: 'uploading' | 'ready' | 'error';
  errorMessage?: string;
  chunks?: number;
  pages?: number;
}

interface ChatAreaProps {
  messages: Message[];
  isStreaming: boolean;
  onSendMessage: (text: string, docFilter?: string[]) => void;
  onStopStreaming: () => void;
  onSelectCitation: (citation: Citation) => void;
  onConfirmFallback?: (approved: boolean) => void;
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

const ATTACHED_DOC_SUGGESTIONS = [
  'Summarize the key takeaways of this document',
  'What are the core topics and sections covered?',
  'Extract important rules, formulas, or policies from this file',
];

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isStreaming,
  onSendMessage,
  onStopStreaming,
  onSelectCitation,
  onConfirmFallback,
  activeThreadTitle,
}) => {
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // Handle sending a message with optional doc_filter
  const handleSend = (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isStreaming) return;

    const readyDocNames = attachedFiles
      .filter((f) => f.status === 'ready')
      .map((f) => f.name);

    onSendMessage(text, readyDocNames.length > 0 ? readyDocNames : undefined);
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

  // Upload one or more selected PDF files specifically for this chat
  const handleFilesSelected = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadError(null);

    const pdfFiles = Array.from(files).filter((file) =>
      file.name.toLowerCase().endsWith('.pdf')
    );

    if (pdfFiles.length === 0) {
      setUploadError('Only PDF files are supported for document chat.');
      setTimeout(() => setUploadError(null), 4000);
      return;
    }

    for (const file of pdfFiles) {
      // Add placeholder state
      const newFileItem: AttachedFile = {
        name: file.name,
        size: file.size,
        status: 'uploading',
      };

      setAttachedFiles((prev) => [
        ...prev.filter((f) => f.name !== file.name),
        newFileItem,
      ]);

      try {
        const res = await uploadDocument(file);
        setAttachedFiles((prev) =>
          prev.map((f) =>
            f.name === file.name
              ? {
                  ...f,
                  status: 'ready',
                  chunks: res.chunks,
                  pages: res.pages,
                }
              : f
          )
        );
      } catch (err: any) {
        setAttachedFiles((prev) =>
          prev.map((f) =>
            f.name === file.name
              ? {
                  ...f,
                  status: 'error',
                  errorMessage: err.message || 'Indexing failed',
                }
              : f
          )
        );
      }
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveFile = (fileName: string) => {
    setAttachedFiles((prev) => prev.filter((f) => f.name !== fileName));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files);
    }
  };

  const readyFiles = attachedFiles.filter((f) => f.status === 'ready');
  const isAnyUploading = attachedFiles.some((f) => f.status === 'uploading');

  const placeholderText =
    readyFiles.length > 0
      ? `Ask a question about ${readyFiles[0].name}${
          readyFiles.length > 1 ? ` and ${readyFiles.length - 1} other file(s)` : ''
        }...`
      : 'Ask a question about your documents... (Shift+Enter for newline)';

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-white dark:bg-gray-950 relative">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => handleFilesSelected(e.target.files)}
        accept=".pdf,application/pdf"
        multiple
        className="hidden"
      />

      {/* Top Navbar */}
      <header className="h-14 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-6 bg-white/70 dark:bg-gray-950/70 backdrop-blur-md shrink-0 z-20">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
          <h2 className="font-semibold text-sm text-gray-800 dark:text-gray-200 truncate max-w-md">
            {!activeThreadTitle ||
            activeThreadTitle.toLowerCase().includes('friendly greeting') ||
            activeThreadTitle.toLowerCase() === 'new chat'
              ? 'New Conversation'
              : activeThreadTitle}
          </h2>
          {readyFiles.length > 0 && (
            <span className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300/60 dark:border-emerald-700/60">
              <FileText className="w-3 h-3" />
              {readyFiles.length} file{readyFiles.length > 1 ? 's' : ''} attached
            </span>
          )}
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
              {readyFiles.length > 0
                ? `Ready to explore ${readyFiles[0].name}`
                : 'How can I help with your documents today?'}
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-8 max-w-md">
              {readyFiles.length > 0
                ? 'Your file has been indexed into this chat. Click a prompt below or type any question to query it.'
                : 'Upload a PDF directly to this chat using the paperclip button, or query any document in the Knowledge Base.'}
            </p>

            {/* Starter Prompt Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
              {(readyFiles.length > 0
                ? ATTACHED_DOC_SUGGESTIONS.map((text, idx) => ({
                    icon: FileText,
                    title: `Option ${idx + 1}`,
                    prompt: text,
                  }))
                : STARTER_PROMPTS
              ).map((starter, idx) => {
                const Icon = starter.icon;
                return (
                  <button
                    key={idx}
                    onClick={() => handleSend(starter.prompt)}
                    className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/40 hover:bg-emerald-50/50 dark:hover:bg-emerald-950/20 hover:border-emerald-500/40 transition text-left group flex flex-col justify-between"
                  >
                    <div>
                      <Icon className="w-5 h-5 text-emerald-600 dark:text-emerald-400 mb-2" />
                      <div className="font-semibold text-xs text-gray-800 dark:text-gray-200 mb-1">
                        {starter.title}
                      </div>
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
              <MessageItem
                key={m.id}
                message={m}
                onSelectCitation={onSelectCitation}
                onConfirmFallback={onConfirmFallback}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Input Area */}
      <div className="p-4 bg-white/80 dark:bg-gray-950/80 backdrop-blur-md border-t border-gray-200 dark:border-gray-800 shrink-0">
        <div className="max-w-3xl mx-auto">
          {/* Upload Error Banner */}
          {uploadError && (
            <div className="mb-2 p-2 rounded-xl bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800/60 text-xs text-red-600 dark:text-red-300 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
                <span>{uploadError}</span>
              </div>
              <button
                onClick={() => setUploadError(null)}
                className="p-1 hover:text-red-800 dark:hover:text-red-100"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Input Container Box with Drag & Drop */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`relative flex flex-col rounded-2xl border transition shadow-sm ${
              isDragging
                ? 'border-emerald-500 bg-emerald-50/30 dark:bg-emerald-950/30 ring-2 ring-emerald-500/40'
                : 'border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 focus-within:border-emerald-500 focus-within:ring-1 focus-within:ring-emerald-500'
            }`}
          >
            {/* Drag and Drop Overlay */}
            {isDragging && (
              <div className="absolute inset-0 bg-emerald-600/10 dark:bg-emerald-500/10 backdrop-blur-xs flex items-center justify-center rounded-2xl z-20 pointer-events-none">
                <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-medium text-xs">
                  <FileUp className="w-5 h-5 animate-bounce" />
                  <span>Drop PDF here to attach to this chat</span>
                </div>
              </div>
            )}

            {/* Attached Files Pills (above textarea) */}
            {attachedFiles.length > 0 && (
              <div className="p-2.5 pb-0 flex flex-wrap gap-2 border-b border-gray-100 dark:border-gray-800/60">
                {attachedFiles.map((file) => (
                  <div
                    key={file.name}
                    className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs border transition ${
                      file.status === 'ready'
                        ? 'bg-emerald-50/70 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200'
                        : file.status === 'uploading'
                        ? 'bg-amber-50/70 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200'
                        : 'bg-red-50/70 dark:bg-red-950/40 border-red-200 dark:border-red-800 text-red-900 dark:text-red-200'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                    <span className="font-medium truncate max-w-[180px] sm:max-w-xs" title={file.name}>
                      {file.name}
                    </span>

                    {/* Status badge */}
                    {file.status === 'uploading' && (
                      <span className="flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        <span>Indexing...</span>
                      </span>
                    )}

                    {file.status === 'ready' && (
                      <span className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 className="w-3 h-3" />
                        {file.chunks ? `${file.chunks} chunks` : 'Ready'}
                      </span>
                    )}

                    {file.status === 'error' && (
                      <span className="flex items-center gap-1 text-[10px] text-red-500">
                        <AlertCircle className="w-3 h-3" />
                        <span>Failed</span>
                      </span>
                    )}

                    {/* Detach button */}
                    <button
                      onClick={() => handleRemoveFile(file.name)}
                      className="p-0.5 rounded-full hover:bg-gray-200/60 dark:hover:bg-gray-800 transition text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                      title="Remove attachment from this chat"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Main Input Row: Paperclip + Textarea + Send Button */}
            <div className="relative flex items-end">
              {/* Attachment / Paperclip Button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isAnyUploading}
                className="p-2.5 ml-1 mb-1 rounded-xl text-gray-500 dark:text-gray-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition disabled:opacity-50"
                title="Attach PDF file to this chat"
              >
                <Paperclip className="w-4 h-4" />
              </button>

              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={handleInputResize}
                onKeyDown={handleKeyDown}
                placeholder={placeholderText}
                className="w-full resize-none max-h-40 py-3.5 pl-2 pr-14 text-sm bg-transparent text-gray-900 dark:text-gray-100 focus:outline-none placeholder-gray-400"
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
                    onClick={() => handleSend()}
                    disabled={!input.trim() || isAnyUploading}
                    className="p-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white transition shadow-sm"
                    title="Send message"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Subtext info */}
          <div className="mt-2 flex items-center justify-between text-[11px] text-gray-400 dark:text-gray-500 px-1">
            <span className="flex items-center gap-1.5">
              <Paperclip className="w-3 h-3" />
              Attach PDF for specific chat
            </span>
            <span>
              {readyFiles.length > 0 ? (
                <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                  Scoped to {readyFiles.length} attached document{readyFiles.length > 1 ? 's' : ''}
                </span>
              ) : (
                'Answers are grounded in ingested PDFs'
              )}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
