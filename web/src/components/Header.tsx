import { useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@workos-inc/authkit-react';
import { Moon, Sun, Menu, LogOut, LogIn, UserPlus, Home, FolderOpen, BookOpen, Upload, Search, PanelLeft } from 'lucide-react';
import SearchBar from './SearchBar.tsx';

interface HeaderProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  onToggleMobileNav: () => void;
  onToggleSidebar: () => void;
  showSidebarToggle: boolean;
}

const desktopNavItems = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/folders/1', icon: FolderOpen, label: 'Drawings', matchPrefix: '/folders' },
  { to: '/manuals', icon: BookOpen, label: 'Manuals' },
  { to: '/submit', icon: Upload, label: 'Submit' },
  { to: '/search?q=', icon: Search, label: 'Search', matchPrefix: '/search' },
];

export default function Header({ darkMode, onToggleDarkMode, onToggleMobileNav, onToggleSidebar, showSidebarToggle }: HeaderProps) {
  const { user, signIn, signUp, signOut, isLoading } = useAuth();
  const location = useLocation();

  const handleSignIn = useCallback(() => { signIn(); }, [signIn]);
  const handleSignUp = useCallback(() => { signUp(); }, [signUp]);
  const handleSignOut = useCallback(() => { signOut(); }, [signOut]);

  const isActive = (item: typeof desktopNavItems[number]) => {
    if (item.to === '/') return location.pathname === '/';
    const prefix = item.matchPrefix ?? item.to.split('?')[0];
    return location.pathname.startsWith(prefix);
  };

  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700">
      <div className="flex items-center gap-2 px-3 py-2 md:px-4 md:py-3">
        {/* Mobile hamburger — opens slide-out nav drawer */}
        <button
          onClick={onToggleMobileNav}
          className="md:hidden p-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 cursor-pointer"
          aria-label="Open menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Mobile sidebar toggle — only on folder/image/bundle pages */}
        {showSidebarToggle && (
          <button
            onClick={onToggleSidebar}
            className="md:hidden p-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 cursor-pointer"
            aria-label="Toggle folder navigation"
          >
            <PanelLeft className="w-5 h-5" />
          </button>
        )}

        {/* Logo / Title */}
        <Link
          to="/"
          className="flex items-center gap-2 flex-shrink-0 no-underline"
        >
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">ST</span>
          </div>
          <div className="hidden sm:block">
            <h1 className="text-base font-semibold text-slate-800 dark:text-slate-100 leading-tight">
              Stearman Hub
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-tight">
              Boeing-Stearman Resource Center
            </p>
          </div>
        </Link>

        {/* Desktop nav links with active states */}
        <nav className="hidden md:flex items-center gap-0.5 ml-4">
          {desktopNavItems.map((item) => {
            const active = isActive(item);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`
                  flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md no-underline
                  transition-colors duration-150
                  ${active
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                    : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }
                `}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Mobile compact search */}
        <div className="flex-1 md:hidden mx-1 min-w-0">
          <SearchBar compact />
        </div>

        {/* Desktop search bar — centered */}
        <div className="flex-1 hidden lg:flex justify-center px-4">
          <SearchBar compact />
        </div>

        {/* Right side controls */}
        <div className="flex items-center gap-1 md:gap-2 ml-auto flex-shrink-0">
          {/* Dark mode toggle */}
          <button
            onClick={onToggleDarkMode}
            className="p-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 cursor-pointer"
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>

          {/* Auth buttons — desktop only; mobile auth is in the nav drawer */}
          {!isLoading && (
            <div className="hidden md:flex items-center gap-1.5">
              {user ? (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2">
                    {user.profilePictureUrl ? (
                      <img
                        src={user.profilePictureUrl}
                        alt={user.firstName ?? 'User'}
                        className="w-7 h-7 rounded-full"
                      />
                    ) : (
                      <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center">
                        <span className="text-white text-xs font-medium">
                          {(user.firstName?.[0] ?? user.email?.[0] ?? 'U').toUpperCase()}
                        </span>
                      </div>
                    )}
                    <span className="text-sm text-slate-700 dark:text-slate-300 max-w-[120px] truncate">
                      {user.firstName ?? user.email}
                    </span>
                  </div>
                  <button
                    onClick={handleSignOut}
                    className="p-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 cursor-pointer"
                    title="Sign out"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={handleSignIn}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md
                      text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
                  >
                    <LogIn className="w-4 h-4" />
                    Log In
                  </button>
                  <button
                    onClick={handleSignUp}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md
                      bg-blue-600 text-white hover:bg-blue-700 cursor-pointer"
                  >
                    <UserPlus className="w-4 h-4" />
                    Sign Up
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
