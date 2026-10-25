import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatArea } from './components/ChatArea';
import { CitationDrawer } from './components/CitationDrawer';
import { DocumentsModal } from './components/DocumentsModal';
import { SettingsModal } from './components/SettingsModal';
import { useChat } from './hooks/useChat';
import { Citation, ChatSettings } from './types';

export const App: React.FC = () => {
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return localStorage.getItem('theme') === 'dark' ||
      (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches);
  });

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isDocsOpen, setIsDocsOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const [settings, setSettings] = useState<ChatSettings>({
    top_k: 8,
    use_reranking: false,
    user_id: 'default',
    answer_mode: 'smart_fallback',
  });

  const {
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
  } = useChat();

  const handleConfirmFallback = (approved: boolean) => {
    // Find the last user query to answer with general AI knowledge or cancel
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (!lastUserMsg) return;
    sendMessage(lastUserMsg.content, settings, undefined, approved);
  };

  // Dark mode effect
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  const activeThread = threads.find((t) => t.id === activeThreadId);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white dark:bg-gray-950 font-sans">
      {/* Sidebar */}
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={selectThread}
        onNewChat={startNewChat}
        onRenameThread={renameThread}
        onDeleteThread={deleteThread}
        onOpenDocuments={() => setIsDocsOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        darkMode={darkMode}
        onToggleDarkMode={() => setDarkMode(!darkMode)}
        isOpen={isSidebarOpen}
        onToggleOpen={() => setIsSidebarOpen(!isSidebarOpen)}
      />

      {/* Main Chat Area */}
      <ChatArea
        messages={messages}
        isStreaming={isStreaming}
        onSendMessage={(text, docFilter) => sendMessage(text, settings, docFilter)}
        onStopStreaming={stopStreaming}
        onSelectCitation={(citation) => setSelectedCitation(citation)}
        onConfirmFallback={handleConfirmFallback}
        activeThreadTitle={activeThread?.title}
      />

      {/* Slide-in Citation Drawer */}
      <CitationDrawer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />

      {/* Documents Modal */}
      <DocumentsModal
        isOpen={isDocsOpen}
        onClose={() => setIsDocsOpen(false)}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={setSettings}
      />
    </div>
  );
};

export default App;
