import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { Citation } from '../types';

interface SourcesPanelProps {
  sources: Citation[];
  onSelectCitation: (citation: Citation) => void;
}

export const SourcesPanel: React.FC<SourcesPanelProps> = ({ sources, onSelectCitation }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mb-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/60 backdrop-blur-sm shadow-sm overflow-hidden transition">
      {/* Header toggle */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 text-xs font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800/40 transition"
      >
        <div className="flex items-center gap-2">
          <BookOpen className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
          <span>Retrieved Document Sources ({sources.length})</span>
        </div>
        <div className="flex items-center gap-1 text-gray-400">
          <span className="text-[11px]">{isExpanded ? 'Hide' : 'Show'}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </button>

      {/* Grid of source cards */}
      {isExpanded && (
        <div className="p-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 border-t border-gray-100 dark:border-gray-800/80 bg-gray-50/50 dark:bg-gray-950/40">
          {sources.map((src) => (
            <div
              key={`src-${src.index}-${src.page_start}`}
              onClick={() => onSelectCitation(src)}
              className="group p-2.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:border-emerald-500/50 dark:hover:border-emerald-500/50 hover:shadow-md cursor-pointer transition flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="flex items-center justify-center w-4 h-4 rounded text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400">
                    {src.index}
                  </span>
                  <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 truncate" title={src.file_name}>
                    {src.file_name}
                  </span>
                </div>
                <div className="text-[11px] text-gray-500 dark:text-gray-400 mb-1 flex items-center gap-1">
                  <FileText className="w-3 h-3 text-gray-400" />
                  <span>p. {src.page_start}</span>
                  {src.section_title && (
                    <span className="truncate max-w-[120px]" title={src.section_title}>
                      • {src.section_title}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-gray-600 dark:text-gray-400 line-clamp-2 leading-relaxed">
                  {src.snippet}
                </p>
              </div>
              <div className="mt-2 text-[10px] text-emerald-600 dark:text-emerald-400 opacity-0 group-hover:opacity-100 font-medium transition">
                View excerpt →
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
