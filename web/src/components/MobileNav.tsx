import { useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@workos-inc/authkit-react';
import {
  X, Home, FolderOpen, BookOpen, Upload, Search,
  LogIn, UserPlus, LogOut, Moon, Sun,
} from 'lucide-react';

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
  darkMode: boolean;
  onToggleDarkMode: () => void;
}

const navItems = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/folders/1', icon: FolderOpen, label: 'Browse Drawings' },
  { to: '/manuals', icon: BookOpen, label: 'Manuals Library' },
  { to: '/submit', icon: Upload, label: 'Submit a Resource' },
  { to: '/search?q=', icon: Search, label: 'Search' },
];

export default function MobileNav({ open, onClose, darkMode, onToggleDarkMode }: MobileNavProps) {
  const location = useLocation();
  const { user, signIn, signUp, signOut, isLoading } = useAuth();

  const handleSignIn = useCallback(() => { signIn(); onClose(); }, [signIn, onClose]);
  const handleSignUp = useCallback(() => { signUp(); onClose(); }, [signUp, onClose]);
  const handleSignOut = useCallback(() => { signOut(); onClose(); }, [signOut, onClose]);

  const isActive = (to: string) => {
    if (to === '/') return location.pathname === '/';
    return location.pathname.startsWith(to.split('?')[0]);
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-50 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 w-72 bg-white dark:bg-slate-900
          border-r border-slate-200 dark:border-slate-700
          transform transition-transform duration-300 ease-in-out md:hidden
          flex flex-col
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Drawer header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">ST</span>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Stearman Hub</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Aviation Resource Center</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 cursor-pointer"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              onClick={onClose}
              className={`
                flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium no-underline
                transition-colors duration-150
                ${isActive(to)
                  ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                  : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                }
              `}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {label}
            </Link>
          ))}
        </nav>

        {/* Bottom section: dark mode + auth */}
        <div className="border-t border-slate-200 dark:border-slate-700 p-4 space-y-3">
          {/* Dark mode */}
          <button
            onClick={onToggleDarkMode}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm
              text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
          >
            {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            {darkMode ? 'Light Mode' : 'Dark Mode'}
          </button>

          {/* Auth */}
          {!isLoading && (
            <>
              {user ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 px-3">
                    {user.profilePictureUrl ? (
                      <img src={user.profilePictureUrl} alt={user.firstName ?? 'User'} className="w-7 h-7 rounded-full" />
                    ) : (
                      <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center">
                        <span className="text-white text-xs font-medium">
                          {(user.firstName?.[0] ?? user.email?.[0] ?? 'U').toUpperCase()}
                        </span>
                      </div>
                    )}
                    <span className="text-sm text-slate-700 dark:text-slate-300 truncate">
                      {user.firstName ?? user.email}
                    </span>
                  </div>
                  <button
                    onClick={handleSignOut}
                    className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm
                      text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 cursor-pointer"
                  >
                    <LogOut className="w-5 h-5" />
                    Sign Out
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <button
                    onClick={handleSignIn}
                    className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm
                      text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
                  >
                    <LogIn className="w-5 h-5" />
                    Log In
                  </button>
                  <button
                    onClick={handleSignUp}
                    className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium
                      bg-blue-600 text-white hover:bg-blue-700 cursor-pointer justify-center"
                  >
                    <UserPlus className="w-5 h-5" />
                    Sign Up
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
