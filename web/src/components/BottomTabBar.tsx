import { Link, useLocation } from 'react-router-dom';
import { Home, FolderOpen, BookOpen, Upload, Search } from 'lucide-react';

const tabs = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/folders/1', icon: FolderOpen, label: 'Drawings', matchPrefix: '/folders' },
  { to: '/search?q=', icon: Search, label: 'Search', matchPrefix: '/search' },
  { to: '/manuals', icon: BookOpen, label: 'Manuals' },
  { to: '/submit', icon: Upload, label: 'Submit' },
];

export default function BottomTabBar() {
  const location = useLocation();

  const isActive = (tab: typeof tabs[number]) => {
    if (tab.to === '/') return location.pathname === '/';
    const prefix = tab.matchPrefix ?? tab.to.split('?')[0];
    return location.pathname.startsWith(prefix);
  };

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm
      border-t border-slate-200 dark:border-slate-700 md:hidden safe-area-bottom">
      <div className="flex items-center justify-around h-14">
        {tabs.map((tab) => {
          const active = isActive(tab);
          return (
            <Link
              key={tab.to}
              to={tab.to}
              className={`
                flex flex-col items-center justify-center gap-0.5 flex-1 h-full no-underline
                transition-colors duration-150 min-w-0
                ${active
                  ? 'text-blue-600 dark:text-blue-400'
                  : 'text-slate-500 dark:text-slate-400'
                }
              `}
            >
              <tab.icon className="w-5 h-5" />
              <span className="text-[10px] font-medium leading-tight truncate">{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
