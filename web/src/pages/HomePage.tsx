import { useNavigate } from 'react-router-dom';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import {
  Image as ImageIcon,
  FolderOpen,
  Search,
  ArrowRight,
  BookOpen,
  Upload,
} from 'lucide-react';
import { useStats, useFolders } from '../api/hooks.ts';
import SearchBar from '../components/SearchBar.tsx';

interface QuickCardProps {
  icon: typeof ImageIcon;
  title: string;
  stat: string;
  description: string;
  color: string;
  hoverBorder: string;
  onClick: () => void;
}

function QuickCard({ icon: Icon, title, stat, description, color, hoverBorder, onClick }: QuickCardProps) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-start gap-3 p-5 sm:p-6 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700
        ${hoverBorder} hover:shadow-lg transition-all duration-200 text-left group cursor-pointer w-full`}
    >
      <div className={`w-12 h-12 ${color} rounded-xl flex items-center justify-center flex-shrink-0`}>
        <Icon className="w-6 h-6" />
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">
            {title}
          </h3>
          <ArrowRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
        </div>
        <p className="text-2xl font-bold text-slate-900 dark:text-slate-50">{stat}</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
      </div>
    </button>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const { data: stats } = useStats();
  const { data: folders } = useFolders();

  usePageMeta(
    'Home',
    'The Boeing-Stearman Information Hub — 7,673 engineering drawings, 36+ technical manuals, full-text search, and community submissions.',
  );

  return (
    <div className="max-w-5xl mx-auto space-y-10 py-8 px-4">
      {/* Hero section */}
      <div className="text-center space-y-4">
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-slate-900 dark:text-slate-50 leading-tight">
          Boeing-Stearman<br />
          <span className="text-blue-600 dark:text-blue-400">Information Hub</span>
        </h1>
        <p className="text-base sm:text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          The complete digital archive of Boeing-Stearman biplane engineering drawings,
          technical manuals, and service documents. Digitized from the original 4-disc set.
        </p>
      </div>

      {/* Search */}
      <div className="flex justify-center">
        <SearchBar />
      </div>

      {/* Quick-access cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <QuickCard
          icon={ImageIcon}
          title="Browse Drawings"
          stat={stats?.total_images?.toLocaleString() ?? '7,673'}
          description="Engineering drawings & frame diagrams"
          color="bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
          hoverBorder="hover:border-blue-300 dark:hover:border-blue-600"
          onClick={() => { const firstFolder = folders?.[0]; if (firstFolder) navigate(`/folders/${firstFolder.id}`); else navigate('/search'); }}
        />
        <QuickCard
          icon={BookOpen}
          title="Manuals Library"
          stat="36+"
          description="Maintenance, parts & pilot handbooks"
          color="bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400"
          hoverBorder="hover:border-amber-300 dark:hover:border-amber-600"
          onClick={() => navigate('/manuals')}
        />
        <QuickCard
          icon={Search}
          title="Search Archive"
          stat={stats?.total_indexes?.toLocaleString() ?? '19,828'}
          description="Drawing numbers, keywords & OCR text"
          color="bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400"
          hoverBorder="hover:border-emerald-300 dark:hover:border-emerald-600"
          onClick={() => navigate('/search?q=')}
        />
        <QuickCard
          icon={Upload}
          title="Submit a Resource"
          stat="Contribute"
          description="Share drawings, manuals & photos"
          color="bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400"
          hoverBorder="hover:border-purple-300 dark:hover:border-purple-600"
          onClick={() => navigate('/submit')}
        />
      </div>

      {/* Folder grid */}
      {folders && folders.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-4">
            Browse by Category
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {folders.map((folder) => (
              <button
                key={folder.id}
                onClick={() => navigate(`/folders/${folder.id}`)}
                className="flex items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700
                  hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md transition-all duration-200
                  text-left group cursor-pointer"
              >
                <FolderOpen className="w-10 h-10 text-blue-500 dark:text-blue-400 flex-shrink-0 p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                    {folder.folder_name}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {folder.image_count > 0
                      ? `${folder.image_count} images`
                      : 'Browse contents'}
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-transform flex-shrink-0" />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Stearman Resources / Partners */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-4 text-center">
          Stearman Resources
        </h2>
        <a
          href="https://yesteryearaviation.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col sm:flex-row items-center gap-4 p-4 rounded-lg
            hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors duration-200 no-underline"
        >
          <img
            src="/yesteryear-logo.jpg"
            alt="Yesteryear Aviation"
            className="h-16 sm:h-12 w-auto object-contain"
          />
          <div className="text-center sm:text-left">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Yesteryear Aviation
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
              Check Yesteryear Aviation for FAA-PMA, New Surplus and As Removed Stearman Parts.
            </p>
          </div>
        </a>
      </div>

      {/* Footer note */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4">
        <p>
          Original data digitized by AirLog Imaging, May 2001.
          Archive maintained by Russ Aviation.
        </p>
      </div>
    </div>
  );
}
