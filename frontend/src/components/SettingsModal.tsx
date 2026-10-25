import React, { useState, useEffect } from 'react';
import { X, Settings2, Brain, Trash2, Sliders, ToggleLeft, ToggleRight, Sparkles } from 'lucide-react';
import { ChatSettings, MemoryItem } from '../types';
import { deleteMemory, fetchMemories } from '../api/client';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: ChatSettings;
  onUpdateSettings: (newSettings: ChatSettings) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
}) => {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loadingMemories, setLoadingMemories] = useState(false);

  const loadMemories = async () => {
    setLoadingMemories(true);
    try {
      const data = await fetchMemories(settings.user_id);
      setMemories(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingMemories(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadMemories();
    }
  }, [isOpen, settings.user_id]);

  const handleDeleteMemory = async (id: string) => {
    try {
      await deleteMemory(id);
      setMemories(memories.filter((m) => m.id !== id));
    } catch (e) {
      console.error('Failed to delete memory', e);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="p-5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
              <Settings2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900 dark:text-white text-base">Retrieval & Memory Settings</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">Tune RAG pipeline parameters & durable memory</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Settings Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Top-K Slider */}
          <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-950/30 space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-sm font-medium text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Retrieved Passages (Top-K)
              </label>
              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                {settings.top_k} chunks
              </span>
            </div>
            <input
              type="range"
              min={2}
              max={15}
              value={settings.top_k}
              onChange={(e) => onUpdateSettings({ ...settings, top_k: parseInt(e.target.value, 10) })}
              className="w-full accent-emerald-600 cursor-pointer"
            />
            <p className="text-xs text-gray-400">Number of candidate document chunks retrieved from ChromaDB.</p>
          </div>

          {/* Cross-Encoder Reranking Toggle */}
          <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-950/30 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Cross-Encoder Reranking
              </div>
              <p className="text-xs text-gray-400 mt-0.5">Use BAAI/bge-reranker-base for enhanced semantic precision</p>
            </div>
            <button
              onClick={() => onUpdateSettings({ ...settings, use_reranking: !settings.use_reranking })}
              className="text-gray-600 dark:text-gray-300 hover:text-emerald-600 dark:hover:text-emerald-400 transition"
            >
              {settings.use_reranking ? (
                <ToggleRight className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <ToggleLeft className="w-8 h-8 text-gray-400" />
              )}
            </button>
          </div>

          {/* Answer Mode Section (Strict / Smart Fallback / Ask Before Fallback) */}
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <Brain className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Knowledge Base Answer Mode
              </label>
              <p className="text-xs text-gray-400 mt-0.5">
                Controls behavior when uploaded documents lack sufficient information to answer a query.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-2.5">
              {/* Option 1: Smart Fallback (Default) */}
              <button
                type="button"
                onClick={() => onUpdateSettings({ ...settings, answer_mode: 'smart_fallback' })}
                className={`p-3 rounded-xl border text-left transition relative flex items-start gap-3 ${
                  settings.answer_mode === 'smart_fallback'
                    ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/30 ring-1 ring-emerald-500/50'
                    : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/60 hover:border-gray-300 dark:hover:border-gray-700'
                }`}
              >
                <div className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${
                  settings.answer_mode === 'smart_fallback'
                    ? 'bg-emerald-500 text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
                }`}>
                  <Sparkles className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-900 dark:text-white">Smart Fallback</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-emerald-100 dark:bg-emerald-900/80 text-emerald-700 dark:text-emerald-300">
                      Recommended
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1 leading-normal">
                    Grounds in documents when possible. If evidence is missing, clearly notifies you and answers using general AI knowledge.
                  </p>
                </div>
              </button>

              {/* Option 2: Ask Before Fallback */}
              <button
                type="button"
                onClick={() => onUpdateSettings({ ...settings, answer_mode: 'ask_before_fallback' })}
                className={`p-3 rounded-xl border text-left transition relative flex items-start gap-3 ${
                  settings.answer_mode === 'ask_before_fallback'
                    ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/30 ring-1 ring-emerald-500/50'
                    : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/60 hover:border-gray-300 dark:hover:border-gray-700'
                }`}
              >
                <div className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${
                  settings.answer_mode === 'ask_before_fallback'
                    ? 'bg-emerald-500 text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
                }`}>
                  <Sliders className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-semibold text-gray-900 dark:text-white">Ask Before Fallback</span>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1 leading-normal">
                    When documents lack evidence, explains that info was not found and requests your confirmation before using general AI knowledge.
                  </p>
                </div>
              </button>

              {/* Option 3: Strict Knowledge Base */}
              <button
                type="button"
                onClick={() => onUpdateSettings({ ...settings, answer_mode: 'strict' })}
                className={`p-3 rounded-xl border text-left transition relative flex items-start gap-3 ${
                  settings.answer_mode === 'strict'
                    ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/30 ring-1 ring-emerald-500/50'
                    : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/60 hover:border-gray-300 dark:hover:border-gray-700'
                }`}
              >
                <div className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${
                  settings.answer_mode === 'strict'
                    ? 'bg-emerald-500 text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
                }`}>
                  <Settings2 className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-semibold text-gray-900 dark:text-white">Strict Knowledge Base Only</span>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1 leading-normal">
                    Strict zero-hallucination policy. Only answers queries directly supported by uploaded documents. Refuses to answer otherwise.
                  </p>
                </div>
              </button>
            </div>
          </div>

          {/* Long-Term Memories Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  Durable User Memories ({memories.length})
                </span>
              </div>
              <button
                onClick={loadMemories}
                className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline"
              >
                Refresh
              </button>
            </div>
            <p className="text-xs text-gray-400">
              Cross-thread facts extracted to personalize interaction style (never cited as facts).
            </p>

            {loadingMemories ? (
              <div className="py-4 text-center text-xs text-gray-400">Loading memories...</div>
            ) : memories.length === 0 ? (
              <div className="py-4 text-center text-xs text-gray-400 border border-gray-200 dark:border-gray-800 rounded-xl">
                No long-term memories extracted yet. As you converse, user preferences are recorded here.
              </div>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {memories.map((m) => (
                  <div
                    key={m.id}
                    className="p-2.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex items-center justify-between text-xs text-gray-700 dark:text-gray-300"
                  >
                    <span className="truncate pr-2">{m.text}</span>
                    <button
                      onClick={() => handleDeleteMemory(m.id)}
                      className="p-1 text-gray-400 hover:text-red-500 transition shrink-0"
                      title="Delete memory"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-gray-800 dark:hover:bg-gray-100 transition shadow-sm"
          >
            Save & Close
          </button>
        </div>
      </div>
    </div>
  );
};
