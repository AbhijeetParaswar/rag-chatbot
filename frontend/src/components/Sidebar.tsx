import React, { useState, useMemo } from 'react';
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

// Clean any legacy generic greeting labels
function getDisplayTitle(title?: string | null): string {
  if (!title) return 'New Chat';
  const trimmed = title.trim();
  const lower = trimmed.toLowerCase();
  if (
    lower.includes('friendly greeting') ||
    lower.includes('greeting and intro') ||
    lower === 'greeting' ||
    lower === 'introduction'
  ) {
    return 'New Chat';
  }
  return trimmed;
}

// Group threads into ChatGPT-style time buckets
function groupThreadsByDate(threads: Thread[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 24 * 60 * 60 * 1000;
  const startOfLast7Days = startOfToday - 7 * 24 * 60 * 60 * 1000;
  const startOfLast30Days = startOfToday - 30 * 24 * 60 * 60 * 1000;

  const groups: { [key: string]: Thread[] } = {
    Today: [],
    Yesterday: [],
    'Previous 7 Days': [],
    'Previous 30 Days': [],
    Older: [],
  };

  for (const t of threads) {
    const rawDate = t.updated_at || t.created_at;
    const dateVal = rawDate
      ? new Date(rawDate.endsWith('Z') ? rawDate : `${rawDate}Z`).getTime()
      : 0;

    if (dateVal >= startOfToday) {
      groups.Today.push(t);
    } else if (dateVal >= startOfYesterday) {
      groups.Yesterday.push(t);
    } else if (dateVal >= startOfLast7Days) {
      groups['Previous 7 Days'].push(t);
    } else if (dateVal >= startOfLast30Days) {
      groups['Previous 30 Days'].push(t);
    } else {
      groups.Older.push(t);
    }
  }

  return groups;
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

  const filteredThreads = useMemo(() => {
    return threads.filter((t) => {
      const display = getDisplayTitle(t.title);
      return display.toLowerCase().includes(search.toLowerCase());
    });
  }, [threads, search]);

  const grouped = useMemo(() => {
    return groupThreadsByDate(filteredThreads);
  }, [filteredThreads]);

  const startEditing = (t: Thread, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(t.id);
    setEditTitle(getDisplayTitle(t.title));
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

  const renderThreadItem = (t: Thread) => {
    const isActive = t.id === activeThreadId;
    const isEditing = t.id === editingId;
    const titleText = getDisplayTitle(t.title);

    return (
      <div
        key={t.id}
        onClick={() => onSelectThread(t.id)}
        className={`group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium cursor-pointer transition-colors duration-150 ${
          isActive
            ? 'bg-gray-200/90 dark:bg-gray-800 text-gray-900 dark:text-white shadow-xs font-semibold'
            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200/60 dark:hover:bg-gray-900/60'
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <MessageSquare
            className={`w-3.5 h-3.5 shrink-0 ${
              isActive
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300'
            }`}
          />
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
            <span
              className="truncate text-left"
              title={titleText}
            >
              {titleText}
            </span>
          )}
        </div>

        {/* Hover Actions: Rename & Delete */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-1">
          {isEditing ? (
            <>
              <button
                onClick={(e) => handleSaveRename(t.id, e)}
                className="p-1 text-emerald-600 hover:text-emerald-700 dark:text-emerald-400"
                title="Save"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleCancelRename}
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                title="Cancel"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </>
          ) : (
            <>
              <button
                onClick={(e) => startEditing(t, e)}
                className="p-1 text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-200 transition-colors"
                title="Rename conversation"
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
                className="p-1 text-gray-400 hover:text-red-500 dark:text-gray-500 dark:hover:text-red-400 transition-colors"
                title="Delete conversation"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <aside className="w-72 md:w-80 h-screen bg-gray-50/90 dark:bg-gray-950 border-r border-gray-200 dark:border-gray-800 flex flex-col justify-between shrink-0 select-none z-30 transition-all duration-200">
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

        {/* ChatGPT Style "New Chat" Button */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs shadow-sm hover:shadow transition group"
        >
          <div className="flex items-center gap-2 font-semibold">
            <Plus className="w-4 h-4 transition-transform group-hover:scale-110" />
            <span>New Chat</span>
          </div>
          <span className="text-[10px] opacity-80 font-mono">3-4 Words</span>
        </button>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 focus:outline-none focus:border-emerald-500 transition"
          />
        </div>
      </div>

      {/* ChatGPT-style Categorized Threads List */}
      <div className="flex-1 overflow-y-auto px-2 space-y-3 py-1">
        {filteredThreads.length === 0 ? (
          <div className="text-center py-10 text-xs text-gray-400">
            {search ? 'No conversations match search' : 'No chats yet'}
          </div>
        ) : search.trim() ? (
          /* Search Results Flat List */
          <div className="space-y-1">
            <div className="px-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1">
              Search Results ({filteredThreads.length})
            </div>
            {filteredThreads.map(renderThreadItem)}
          </div>
        ) : (
          /* ChatGPT Style Date-Grouped Sections */
          Object.entries(grouped).map(([label, groupThreads]) => {
            if (groupThreads.length === 0) return null;
            return (
              <div key={label} className="space-y-1">
                <div className="px-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                  {label}
                </div>
                {groupThreads.map(renderThreadItem)}
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
