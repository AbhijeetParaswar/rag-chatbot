import React, { useState, useEffect } from 'react';
import { X, Upload, FileText, CheckCircle2, AlertCircle, Loader2, RefreshCw, FolderSync } from 'lucide-react';
import { DocumentItem } from '../types';
import { fetchDocuments, uploadDocument, syncDocuments } from '../api/client';

interface DocumentsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentsModal: React.FC<DocumentsModalProps> = ({ isOpen, onClose }) => {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadDocs = async () => {
    setLoading(true);
    try {
      const data = await fetchDocuments();
      setDocs(data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setStatusMessage(null);
    try {
      const res = await syncDocuments();
      const indexed = res.filter((r: any) => r.status === 'indexed').length;
      setStatusMessage({
        type: 'success',
        text: `Sync complete: ${indexed} new/updated document(s) indexed from data/pdfs folder.`,
      });
      await loadDocs();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Failed to sync documents from disk folder',
      });
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadDocs();
      setStatusMessage(null);
    }
  }, [isOpen]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setStatusMessage(null);
    try {
      const res = await uploadDocument(file);
      setStatusMessage({
        type: 'success',
        text: `Indexed "${res.file_name}": ${res.chunks} chunks created across ${res.pages} pages.`,
      });
      await loadDocs();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Failed to upload document',
      });
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="p-5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900 dark:text-white text-base">Knowledge Base Documents</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">Upload PDFs to ingest and search against</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Upload Dropzone */}
          <div className="relative border-2 border-dashed border-gray-300 dark:border-gray-700 hover:border-emerald-500 dark:hover:border-emerald-500 rounded-xl p-6 text-center transition bg-gray-50/50 dark:bg-gray-950/30">
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={uploading}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            />
            <div className="flex flex-col items-center justify-center gap-2 pointer-events-none">
              {uploading ? (
                <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
              ) : (
                <Upload className="w-8 h-8 text-gray-400 group-hover:text-emerald-500 transition" />
              )}
              <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {uploading ? 'Processing and indexing PDF chunks...' : 'Click or drag a PDF here to upload'}
              </div>
              <p className="text-xs text-gray-400">Automatic SHA-256 deduplication and semantic chunking</p>
            </div>
          </div>

          {/* Feedback Alert */}
          {statusMessage && (
            <div
              className={`p-3.5 rounded-xl text-xs flex items-center gap-2.5 ${
                statusMessage.type === 'success'
                  ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800'
                  : 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
              }`}
            >
              {statusMessage.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
              )}
              <span>{statusMessage.text}</span>
            </div>
          )}

          {/* Documents List */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                Indexed Documents ({docs.length})
              </span>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleSync}
                  disabled={syncing || loading}
                  className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 font-medium flex items-center gap-1.5 transition disabled:opacity-50"
                  title="Scan data/pdfs folder and index any new or updated PDF files"
                >
                  <FolderSync className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                  {syncing ? 'Syncing...' : 'Sync Disk Folder'}
                </button>
                <span className="text-gray-300 dark:text-gray-700">|</span>
                <button
                  onClick={loadDocs}
                  disabled={loading || syncing}
                  className="text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 flex items-center gap-1 transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
              </div>
            </div>

            {loading && docs.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400">Loading documents...</div>
            ) : docs.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400 border border-gray-100 dark:border-gray-800 rounded-xl">
                No documents uploaded yet. Upload a PDF above to begin!
              </div>
            ) : (
              <div className="space-y-2">
                {docs.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800/40 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{doc.file_name}</p>
                        <p className="text-xs text-gray-400">
                          {doc.pages} pages • {doc.chunk_count} chunks • Hash: {doc.hash.slice(0, 8)}...
                        </p>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 text-[11px] font-medium rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 shrink-0">
                      Active
                    </span>
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
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
