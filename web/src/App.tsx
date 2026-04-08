import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { useAuth } from '@workos-inc/authkit-react';
import { setAuthToken } from './api/client.ts';
import Header from './components/Header.tsx';
import FolderTree from './components/FolderTree.tsx';
import MobileNav from './components/MobileNav.tsx';
import BottomTabBar from './components/BottomTabBar.tsx';
import HomePage from './pages/HomePage.tsx';
import FolderPage from './pages/FolderPage.tsx';
import ImagePage from './pages/ImagePage.tsx';
import BundlePage from './pages/BundlePage.tsx';
import SearchPage from './pages/SearchPage.tsx';
import ManualsPage from './pages/ManualsPage.tsx';
import SubmitPage from './pages/SubmitPage.tsx';

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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { getAccessToken } = useAuth();
  const location = useLocation();

  // Close drawers on route change
  useEffect(() => {
    setMobileNavOpen(false);
    setSidebarOpen(false);
  }, [location.pathname]);

  // Show folder sidebar on folder/image/bundle pages
  const showSidebar = /^\/(folders|images|bundles)/.test(location.pathname);

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

  const toggleMobileNav = useCallback(() => {
    setMobileNavOpen((prev) => !prev);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200">
      <Header
        darkMode={darkMode}
        onToggleDarkMode={toggleDarkMode}
        onToggleMobileNav={toggleMobileNav}
        onToggleSidebar={toggleSidebar}
        showSidebarToggle={showSidebar}
      />

      <MobileNav
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        darkMode={darkMode}
        onToggleDarkMode={toggleDarkMode}
      />

      <div className="flex h-[calc(100vh-64px)]">
        {/* Sidebar overlay for mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/40 z-30 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Folder sidebar — desktop: always visible on folder/image/bundle pages; mobile: toggled */}
        {showSidebar && (
          <aside
            className={`
              fixed md:static inset-y-0 left-0 z-30
              w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700
              overflow-y-auto flex-shrink-0
              transform transition-transform duration-200 ease-in-out
              ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
              md:translate-x-0
              top-0 md:top-auto pt-16 md:pt-0
            `}
          >
            <div className="p-3 border-b border-slate-200 dark:border-slate-700">
              <h2 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Folder Navigation
              </h2>
            </div>
            <FolderTree />
          </aside>
        )}

        {/* Main content — bottom padding for mobile tab bar */}
        <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/folders/:id" element={<FolderPage />} />
            <Route path="/images/:id" element={<ImagePage />} />
            <Route path="/bundles/:id" element={<BundlePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/manuals" element={<ManualsPage />} />
            <Route path="/submit" element={<SubmitPage />} />
          </Routes>
        </main>
      </div>

      <BottomTabBar />
    </div>
  );
}
