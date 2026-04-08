import { useNavigate } from 'react-router-dom';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import {
  Image as ImageIcon,
  FolderOpen,
  Layers,
  Search,
  ArrowRight,
  BookOpen,
  FileText,
} from 'lucide-react';
import { useStats, useFolders } from '../api/hooks.ts';
import SearchBar from '../components/SearchBar.tsx';

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof ImageIcon;
  label: string;
  value: number | string;
}) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 text-center">
      <Icon className="w-8 h-8 mx-auto text-blue-500 dark:text-blue-400 mb-2" />
      <p className="text-2xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
    </div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const { data: stats } = useStats();
  const { data: folders } = useFolders();

  usePageMeta(
    'Home',
    'Complete searchable archive of 7,673 Boeing-Stearman engineering drawings, frame diagrams, and service manual pages.',
  );

  return (
    <div className="max-w-4xl mx-auto space-y-10 py-8 px-4">
      {/* Hero section */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-sm font-medium">
          <Layers className="w-4 h-4" />
          7,673 Engineering Drawings
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-slate-50 leading-tight">
          Stearman Parts &<br />Service Guide
        </h1>
        <p className="text-lg text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
          Browse the complete archive of Boeing-Stearman biplane engineering drawings,
          frame diagrams, and service manual pages. Digitized from the original 4-disc set.
        </p>
      </div>

      {/* Search */}
      <div className="flex justify-center">
        <SearchBar />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={ImageIcon}
          label="Total Images"
          value={stats?.total_images?.toLocaleString() ?? '7,673'}
        />
        <StatCard
          icon={FolderOpen}
          label="Folders"
          value={stats?.total_folders ?? 17}
        />
        <StatCard
          icon={Layers}
          label="Bundles"
          value={stats?.total_bundles ?? 396}
        />
        <StatCard
          icon={Search}
          label="Index Records"
          value={stats?.total_indexes?.toLocaleString() ?? '19,828'}
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

      {/* Technical Manuals — prominent section */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-4">
          Technical Manuals
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            onClick={() => navigate('/manuals')}
            className="flex items-center gap-4 p-5 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700
              hover:border-amber-300 dark:hover:border-amber-600 hover:shadow-md transition-all duration-200
              text-left group cursor-pointer"
          >
            <div className="w-12 h-12 bg-amber-50 dark:bg-amber-900/30 rounded-xl flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-6 h-6 text-amber-600 dark:text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                Erection & Maintenance Instructions
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                PT-13D / N2S-5 · View online or download PDF
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-amber-500 group-hover:translate-x-0.5 transition-transform flex-shrink-0" />
          </button>
          <button
            onClick={() => navigate('/manuals')}
            className="flex items-center gap-4 p-5 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700
              hover:border-amber-300 dark:hover:border-amber-600 hover:shadow-md transition-all duration-200
              text-left group cursor-pointer"
          >
            <div className="w-12 h-12 bg-amber-50 dark:bg-amber-900/30 rounded-xl flex items-center justify-center flex-shrink-0">
              <FileText className="w-6 h-6 text-amber-600 dark:text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                Parts Catalog
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                PT-13D / N2S-5 · View online or download PDF
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-amber-500 group-hover:translate-x-0.5 transition-transform flex-shrink-0" />
          </button>
        </div>
      </div>

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
