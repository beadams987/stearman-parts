import { useEffect, useState } from 'react';
import { FileText, Download, BookOpen, Eye, X } from 'lucide-react';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import apiClient from '../api/client.ts';

interface Manual {
  id: string;
  title: string;
  description: string;
  filename: string;
  size_mb: number;
  download_url: string;
  view_url: string;
}

export default function ManualsPage() {
  const [manuals, setManuals] = useState<Manual[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewingManual, setViewingManual] = useState<Manual | null>(null);

  usePageMeta(
    'Technical Manuals',
    'View and download official Boeing-Stearman reference manuals: Erection & Maintenance Instructions and Parts Catalog for PT-13D / N2S-5.',
  );

  useEffect(() => {
    apiClient
      .get<Manual[]>('/manuals')
      .then((res: { data: Manual[] }) => setManuals(res.data))
      .catch(() => setManuals([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-8 py-8 px-4">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-sm font-medium">
          <BookOpen className="w-4 h-4" />
          Reference Manuals
        </div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-50">
          Technical Manuals
        </h1>
        <p className="text-lg text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
          Official Boeing-Stearman reference manuals — view online or download.
          Public-domain documents covering erection, maintenance, and parts
          identification for the PT-13D and N2S-5.
        </p>
      </div>

      {/* Manual cards */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {manuals.map((manual) => (
            <div
              key={manual.id}
              className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 flex flex-col gap-4 hover:shadow-lg transition-shadow duration-200"
            >
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 bg-red-50 dark:bg-red-900/30 rounded-xl flex items-center justify-center flex-shrink-0">
                  <FileText className="w-7 h-7 text-red-600 dark:text-red-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 leading-snug">
                    {manual.title}
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {manual.description}
                  </p>
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 uppercase tracking-wide">
                    PDF · {manual.size_mb} MB
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 mt-auto pt-3 border-t border-slate-100 dark:border-slate-700">
                <button
                  onClick={() => setViewingManual(manual)}
                  className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg
                    border border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400
                    hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors duration-150 cursor-pointer"
                >
                  <Eye className="w-4 h-4" />
                  View Online
                </button>
                <a
                  href={manual.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg
                    bg-blue-600 text-white hover:bg-blue-700 transition-colors duration-150"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Note */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4">
        <p>
          These manuals are U.S. government publications in the public domain.
        </p>
      </div>

      {/* Google Docs PDF Viewer Modal */}
      {viewingManual && (
        <div className="fixed inset-0 z-50 bg-black/80 flex flex-col">
          {/* Viewer header */}
          <div className="flex items-center justify-between px-4 py-3 bg-slate-900 text-white">
            <div className="flex items-center gap-3 min-w-0">
              <BookOpen className="w-5 h-5 text-amber-400 flex-shrink-0" />
              <div className="min-w-0">
                <h2 className="text-sm font-semibold truncate">{viewingManual.title}</h2>
                <p className="text-xs text-slate-400">{viewingManual.description}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <a
                href={viewingManual.download_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                  bg-blue-600 text-white hover:bg-blue-700 transition-colors duration-150"
              >
                <Download className="w-4 h-4" />
                <span className="hidden sm:inline">Download PDF</span>
              </a>
              <button
                onClick={() => setViewingManual(null)}
                className="p-2 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer"
                aria-label="Close viewer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Google Docs Viewer iframe */}
          <div className="flex-1 bg-slate-800 relative">
            <iframe
              src={viewingManual.view_url}
              className="w-full h-full border-0"
              title={viewingManual.title}
              sandbox="allow-scripts allow-same-origin allow-popups"
            />
            {/* Loading indicator */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="bg-slate-900/70 rounded-lg px-4 py-3 text-slate-300 text-sm animate-pulse">
                Loading document...
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
