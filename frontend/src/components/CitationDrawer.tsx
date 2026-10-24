import React from 'react';
import { X, FileText, Bookmark, ExternalLink } from 'lucide-react';
import { Citation } from '../types';

interface CitationDrawerProps {
  citation: Citation | null;
  onClose: () => void;
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({ citation, onClose }) => {
  if (!citation) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 shadow-2xl flex flex-col transition-transform duration-300 ease-in-out">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50">
        <div className="flex items-center gap-2">
          <span className="flex items-center justify-center w-7 h-7 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 font-semibold text-sm">
            [{citation.index}]
          </span>
          <h3 className="font-semibold text-gray-900 dark:text-white text-base truncate">
            Source Passage
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          aria-label="Close drawer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Metadata Badges */}
      <div className="p-4 bg-gray-50 dark:bg-gray-800/40 border-b border-gray-200 dark:border-gray-800 flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
          <FileText className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="font-medium truncate">{citation.file_name}</span>
        </div>
        <div className="flex items-center gap-4 text-gray-600 dark:text-gray-400">
          <span>
            <strong className="text-gray-900 dark:text-gray-200">Page:</strong>{' '}
            {citation.page_start === citation.page_end
              ? citation.page_start
              : `${citation.page_start}–${citation.page_end}`}
          </span>
          {citation.section_title && (
            <span className="truncate">
              <strong className="text-gray-900 dark:text-gray-200">Section:</strong>{' '}
              {citation.section_title}
            </span>
          )}
        </div>
      </div>

      {/* Content passage */}
      <div className="flex-1 p-5 overflow-y-auto">
        <div className="text-xs uppercase tracking-wider text-gray-400 dark:text-gray-500 font-semibold mb-2 flex items-center gap-1.5">
          <Bookmark className="w-3.5 h-3.5" />
          Exact Document Excerpt
        </div>
        <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-950 border border-gray-200 dark:border-gray-800 text-sm leading-relaxed text-gray-800 dark:text-gray-200 font-sans whitespace-pre-wrap select-text">
          {citation.snippet}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 flex justify-end">
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-200 dark:bg-gray-800 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-700 transition"
        >
          Close
        </button>
      </div>
    </div>
  );
};
