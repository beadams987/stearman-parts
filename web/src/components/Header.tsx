import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@workos-inc/authkit-react';
import { Moon, Sun, Menu, LogOut, LogIn, UserPlus, BookOpen, Upload } from 'lucide-react';
import SearchBar from './SearchBar.tsx';

interface HeaderProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  onToggleSidebar: () => void;
}

export default function Header({ darkMode, onToggleDarkMode, onToggleSidebar }: HeaderProps) {
  const { user, signIn, signUp, signOut, isLoading } = useAuth();

  const handleSignIn = useCallback(() => {
    signIn();
  }, [signIn]);

  const handleSignUp = useCallback(() => {
    signUp();
  }, [signUp]);

  const handleSignOut = useCallback(() => {
    signOut();
  }, [signOut]);

  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700">
      <div className="flex items-center gap-4 px-4 py-3">
        {/* Mobile sidebar toggle */}
        <button
          onClick={onToggleSidebar}
          className="lg:hidden p-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 cursor-pointer"
          aria-label="Toggle sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

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
              Stearman Parts & Service Guide
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-tight">
              Engineering Drawings Archive
            </p>
          </div>
        </Link>

        {/* Nav links */}
        <nav className="hidden md:flex items-center gap-1 ml-4">
          <Link
            to="/manuals"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md
              text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 no-underline"
          >
            <BookOpen className="w-4 h-4" />
            Manuals
          </Link>
          <Link
            to="/submit"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md
              text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 no-underline"
          >
            <Upload className="w-4 h-4" />
            Submit
          </Link>
        </nav>

        {/* Search bar - center */}
        <div className="flex-1 hidden md:flex justify-center px-4">
          <SearchBar compact />
        </div>

        {/* Right side controls */}
        <div className="flex items-center gap-2 ml-auto flex-shrink-0">
          {/* Dark mode toggle */}
          <button
            onClick={onToggleDarkMode}
            className="p-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 cursor-pointer"
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>

          {/* Auth buttons */}
          {!isLoading && (
            <>
              {user ? (
                <div className="flex items-center gap-2">
                  <div className="hidden sm:flex items-center gap-2">
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
                    <span className="hidden sm:inline">Log In</span>
                  </button>
                  <button
                    onClick={handleSignUp}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md
                      bg-blue-600 text-white hover:bg-blue-700 cursor-pointer"
                  >
                    <UserPlus className="w-4 h-4" />
                    <span className="hidden sm:inline">Sign Up</span>
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Mobile search bar */}
      <div className="md:hidden px-4 pb-3">
        <SearchBar compact />
      </div>
    </header>
  );
}
