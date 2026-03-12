import { useState, useEffect, useCallback } from 'react';
import { Routes, Route } from 'react-router-dom';
import { useAuth } from '@workos-inc/authkit-react';
import { setAuthToken } from './api/client.ts';
import Header from './components/Header.tsx';
import FolderTree from './components/FolderTree.tsx';
import HomePage from './pages/HomePage.tsx';
import FolderPage from './pages/FolderPage.tsx';
import ImagePage from './pages/ImagePage.tsx';
import BundlePage from './pages/BundlePage.tsx';
import SearchPage from './pages/SearchPage.tsx';

function useDarkMode() {
  const [darkMode, setDarkMode] = useState(() => {
    const stored = localStorage.getItem('stearman-dark-mode');
    if (stored !== null) return stored === 'true';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('stearman-dark-mode', String(darkMode));
  }, [darkMode]);

  const toggle = useCallback(() => setDarkMode((prev) => !prev), []);

  return { darkMode, toggle };
}

export default function App() {
  const { darkMode, toggle: toggleDarkMode } = useDarkMode();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { getAccessToken } = useAuth();

  // Sync auth token to API client
  useEffect(() => {
    async function syncToken() {
      try {
        const token = await getAccessToken();
        setAuthToken(token);
      } catch {
        setAuthToken(null);
      }
    }
    syncToken();
  }, [getAccessToken]);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200">
      <Header
        darkMode={darkMode}
        onToggleDarkMode={toggleDarkMode}
        onToggleSidebar={toggleSidebar}
      />

      <div className="flex h-[calc(100vh-64px)]">
        {/* Sidebar overlay for mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/40 z-30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`
            fixed lg:static inset-y-0 left-0 z-30
            w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700
            overflow-y-auto flex-shrink-0
            transform transition-transform duration-200 ease-in-out
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
            lg:translate-x-0
            top-0 lg:top-auto pt-16 lg:pt-0
          `}
        >
          <div className="p-3 border-b border-slate-200 dark:border-slate-700">
            <h2 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Folder Navigation
            </h2>
          </div>
          <FolderTree />
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/folders/:id" element={<FolderPage />} />
            <Route path="/images/:id" element={<ImagePage />} />
            <Route path="/bundles/:id" element={<BundlePage />} />
            <Route path="/search" element={<SearchPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
