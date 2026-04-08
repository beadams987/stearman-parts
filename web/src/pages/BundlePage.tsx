import { useParams, Link } from 'react-router-dom';
import { ChevronRight, Home, ArrowLeft } from 'lucide-react';
import { useBundle } from '../api/hooks.ts';
import BundleViewer from '../components/BundleViewer.tsx';

export default function BundlePage() {
  const { id } = useParams<{ id: string }>();
  const bundleId = id ? Number(id) : undefined;

  const { data: bundle, isLoading, error } = useBundle(bundleId);

  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <div className="skeleton h-6 w-64 rounded" />
        <div className="skeleton h-12 rounded-lg" />
        <div className="skeleton h-[500px] rounded-lg" />
        <div className="skeleton h-24 rounded-lg" />
      </div>
    );
  }

  if (error || !bundle) {
    return (
      <div className="text-center py-16">
        <p className="text-lg text-slate-500 dark:text-slate-400 mb-4">
          Bundle not found.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 h-full flex flex-col">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400 flex-shrink-0">
        <Link
          to="/"
          className="flex items-center gap-1 hover:text-amber-700 dark:hover:text-amber-400"
        >
          <Home className="w-3.5 h-3.5" />
          <span>Home</span>
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <Link
          to={`/folders/${bundle.folder_id}`}
          className="hover:text-amber-700 dark:hover:text-amber-400"
        >
          {bundle.folder_name}
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="text-slate-800 dark:text-slate-200 font-medium">
          Bundle ({bundle.pages.length} pages)
        </span>
      </nav>

      {/* Bundle header */}
      <div className="flex-shrink-0">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
          Multi-Page Drawing Bundle
        </h1>
        <div className="flex flex-wrap gap-2 mt-2">
          {bundle.drawing_numbers.map((dn) => (
            <span
              key={dn}
              className="inline-block px-2 py-0.5 text-xs font-mono bg-amber-50 dark:bg-amber-900/30
                text-amber-800 dark:text-amber-300 rounded-md border border-amber-200 dark:border-amber-800"
            >
              {dn}
            </span>
          ))}
          {bundle.keywords.map((kw) => (
            <span
              key={kw}
              className="inline-block px-2 py-0.5 text-xs bg-slate-100 dark:bg-slate-700
                text-slate-700 dark:text-slate-300 rounded-md"
            >
              {kw}
            </span>
          ))}
        </div>
      </div>

      {/* Bundle viewer */}
      <div className="flex-1 min-h-0">
        <BundleViewer
          pages={bundle.pages}
          drawingNumbers={bundle.drawing_numbers}
          keywords={bundle.keywords}
          folderName={bundle.folder_name}
          notes={bundle.notes}
        />
      </div>
    </div>
  );
}
