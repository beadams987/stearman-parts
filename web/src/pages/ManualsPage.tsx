import { useEffect, useState } from 'react';
import { FileText, Download, BookOpen } from 'lucide-react';
import apiClient from '../api/client.ts';

interface Manual {
  id: string;
  title: string;
  description: string;
  filename: string;
  size_mb: number;
}

export default function ManualsPage() {
  const [manuals, setManuals] = useState<Manual[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get<Manual[]>('/manuals')
      .then((res: { data: Manual[] }) => setManuals(res.data))
      .catch(() => {
        // Fallback to hardcoded if API is unreachable
        setManuals([
          {
            id: 'erection-maintenance',
            title: 'Erection & Maintenance Instructions',
            description: 'Army Model PT-13D and Navy Model N2S-5',
            filename: '',
            size_mb: 23,
          },
          {
            id: 'parts-catalog',
            title: 'Parts Catalog',
            description: 'Army Model PT-13D and Navy Model N2S-5',
            filename: '',
            size_mb: 149,
          },
        ]);
      })
      .finally(() => setLoading(false));
  }, []);

  const apiBase = import.meta.env.VITE_API_URL || '';

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-8 px-4">
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
          Official Boeing-Stearman reference manuals available for download.
          These public-domain documents cover erection, maintenance, and parts
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
                <div className="w-12 h-12 bg-red-50 dark:bg-red-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText className="w-6 h-6 text-red-600 dark:text-red-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 leading-snug">
                    {manual.title}
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {manual.description}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between mt-auto pt-2 border-t border-slate-100 dark:border-slate-700">
                <span className="text-xs text-slate-400 dark:text-slate-500 uppercase tracking-wide">
                  PDF · {manual.size_mb} MB
                </span>
                <a
                  href={`${apiBase}/api/manuals/${manual.id}/download`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                    bg-blue-600 text-white hover:bg-blue-700 transition-colors duration-150"
                >
                  <Download className="w-4 h-4" />
                  Download
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
    </div>
  );
}
