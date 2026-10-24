import React, { useState } from 'react';
import {
  Plus,
  MessageSquare,
  Search,
  Trash2,
  Edit2,
  Check,
  X,
  FileText,
  Settings as SettingsIcon,
  Moon,
  Sun,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { Thread } from '../types';

interface SidebarProps {
  threads: Thread[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onRenameThread: (threadId: string, newTitle: string) => void;
  onDeleteThread: (threadId: string) => void;
  onOpenDocuments: () => void;
  onOpenSettings: () => void;
  darkMode: boolean;
  onToggleDarkMode: () => void;
  isOpen: boolean;
  onToggleOpen: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  threads,
  activeThreadId,
  onSelectThread,
  onNewChat,
  onRenameThread,
  onDeleteThread,
  onOpenDocuments,
  onOpenSettings,
  darkMode,
  onToggleDarkMode,
  isOpen,
  onToggleOpen,
}) => {
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const filteredThreads = threads.filter((t) =>
    (t.title || 'New Chat').toLowerCase().includes(search.toLowerCase())
  );

  const startEditing = (t: Thread, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(t.id);
    setEditTitle(t.title || 'New Chat');
  };

  const handleSaveRename = (threadId: string, e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onRenameThread(threadId, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  if (!isOpen) {
    return (
      <div className="fixed top-3 left-3 z-30">
        <button
          onClick={onToggleOpen}
          className="p-2 rounded-xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-md text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
          title="Open Sidebar"
        >
          <PanelLeftOpen className="w-5 h-5" />
        </button>
      </div>
    );
  }

  return (
    <aside className="w-72 md:w-80 h-screen bg-gray-100/70 dark:bg-gray-950 border-r border-gray-200 dark:border-gray-800 flex flex-col justify-between shrink-0 select-none z-30 transition-all duration-200">
      {/* Top Header & Actions */}
      <div className="p-3.5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-bold text-base shadow-sm">
              D
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-tight text-gray-900 dark:text-white">DocuRAG</h1>
              <p className="text-[10px] text-gray-500 font-medium tracking-wide uppercase">Precision Document Assistant</p>
            </div>
          </div>
          <button
            onClick={onToggleOpen}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-200/60 dark:hover:bg-gray-800 transition"
            title="Collapse Sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm transition shadow-sm hover:shadow"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </button>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-gray-400" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 focus:outline-none focus:border-emerald-500 transition"
          />
        </div>
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1 py-1">
        <div className="px-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1">
          Recent Chats ({filteredThreads.length})
        </div>

        {filteredThreads.length === 0 ? (
          <div className="text-center py-8 text-xs text-gray-400">
            {search ? 'No conversations match search' : 'No chats yet'}
          </div>
        ) : (
          filteredThreads.map((t) => {
            const isActive = t.id === activeThreadId;
            const isEditing = t.id === editingId;

            return (
              <div
                key={t.id}
                onClick={() => onSelectThread(t.id)}
                className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium cursor-pointer transition ${
                  isActive
                    ? 'bg-white dark:bg-gray-800/80 text-emerald-700 dark:text-emerald-400 shadow-sm border border-gray-200/80 dark:border-gray-700/60'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200/50 dark:hover:bg-gray-900/50'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-400'}`} />
                  {isEditing ? (
                    <input
                      type="text"
                      autoFocus
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveRename(t.id, e);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      className="bg-transparent border-b border-emerald-500 text-xs text-gray-900 dark:text-white focus:outline-none w-full"
                    />
                  ) : (
                    <span className="truncate">{t.title || 'New Chat'}</span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition shrink-0 ml-1">
                  {isEditing ? (
                    <>
                      <button
                        onClick={(e) => handleSaveRename(t.id, e)}
                        className="p-1 text-emerald-600 hover:text-emerald-700"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={handleCancelRename} className="p-1 text-gray-400 hover:text-gray-600">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={(e) => startEditing(t, e)}
                        className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                        title="Rename"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this conversation?')) {
                            onDeleteThread(t.id);
                          }
                        }}
                        className="p-1 text-gray-400 hover:text-red-500"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Bottom Nav: Documents, Settings, Theme */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-800 space-y-1">
        <button
          onClick={onOpenDocuments}
          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-200/50 dark:hover:bg-gray-900/50 transition"
        >
          <FileText className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span>Knowledge Base PDFs</span>
        </button>

        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-200/50 dark:hover:bg-gray-900/50 transition"
        >
          <SettingsIcon className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span>Retrieval Settings & Memory</span>
        </button>

        <button
          onClick={onToggleDarkMode}
          className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-200/50 dark:hover:bg-gray-900/50 transition"
        >
          <div className="flex items-center gap-2.5">
            {darkMode ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-indigo-500" />}
            <span>{darkMode ? 'Light Mode' : 'Dark Mode'}</span>
          </div>
          <span className="text-[10px] text-gray-400 capitalize">{darkMode ? 'Dark' : 'Light'}</span>
        </button>
      </div>
    </aside>
  );
};
