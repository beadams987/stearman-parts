import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  FileText, Download, BookOpen, Eye, X, Search,
  Filter, ChevronLeft, ChevronRight, Library,
} from 'lucide-react';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import apiClient from '../api/client.ts';

interface Manual {
  id: string;
  title: string;
  description: string;
  category: string;
  filename: string;
  size_mb: number;
  page_count: number;
  download_url: string;
  view_url: string;
}

interface ManualPageResult {
  manual_id: string;
  manual_title: string;
  page_number: number;
  snippet: string;
  view_url: string;
}

interface ManualSearchResponse {
  results: ManualPageResult[];
  total: number;
  query: string;
}

type ViewMode = 'library' | 'viewer';

export default function ManualsPage() {
  const [manuals, setManuals] = useState<Manual[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewingManual, setViewingManual] = useState<Manual | null>(null);
  const [viewerUrl, setViewerUrl] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('library');

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ManualPageResult[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searching, setSearching] = useState(false);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  // Search match navigation
  const [currentMatchIdx, setCurrentMatchIdx] = useState(0);

  usePageMeta(
    'Technical Manuals Library',
    'Browse, search, and view official Boeing-Stearman reference manuals. Full-text search across all manual pages.',
  );

  useEffect(() => {
    apiClient
      .get<Manual[]>('/manuals')
      .then((res: { data: Manual[] }) => setManuals(res.data))
      .catch(() => setManuals([]))
      .finally(() => setLoading(false));
  }, []);

  // Debounced search
  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults([]);
      setSearchTotal(0);
      return;
    }
    const timer = setTimeout(() => {
      setSearching(true);
      apiClient
        .get<ManualSearchResponse>('/manuals/search', { params: { q: searchQuery } })
        .then((res: { data: ManualSearchResponse }) => {
          setSearchResults(res.data.results);
          setSearchTotal(res.data.total);
          setCurrentMatchIdx(0);
        })
        .catch(() => {
          setSearchResults([]);
          setSearchTotal(0);
        })
        .finally(() => setSearching(false));
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Get unique categories
  const categories = useMemo(
    () => [...new Set(manuals.map((m) => m.category))].sort(),
    [manuals],
  );

  // Filtered manuals
  const filteredManuals = useMemo(
    () => activeFilter ? manuals.filter((m) => m.category === activeFilter) : manuals,
    [manuals, activeFilter],
  );

  const openViewer = useCallback((manual: Manual, url?: string) => {
    setViewingManual(manual);
    setViewerUrl(url || manual.view_url);
    setViewMode('viewer');
  }, []);

  const openSearchResult = useCallback((result: ManualPageResult) => {
    const manual = manuals.find((m) =>
      m.id === result.manual_id ||
      result.manual_id.includes(m.id) ||
      m.filename.includes(result.manual_id),
    );
    if (manual) {
      openViewer(manual, result.view_url);
    }
  }, [manuals, openViewer]);

  const closeViewer = useCallback(() => {
    setViewMode('library');
    setViewingManual(null);
    setViewerUrl('');
  }, []);

  // Navigate between search matches while in viewer
  const navigateMatch = useCallback((direction: 'prev' | 'next') => {
    if (searchResults.length === 0) return;
    const newIdx = direction === 'next'
      ? Math.min(currentMatchIdx + 1, searchResults.length - 1)
      : Math.max(currentMatchIdx - 1, 0);
    setCurrentMatchIdx(newIdx);
    const result = searchResults[newIdx];
    const manual = manuals.find((m) =>
      m.id === result.manual_id ||
      result.manual_id.includes(m.id) ||
      m.filename.includes(result.manual_id),
    );
    if (manual) {
      setViewingManual(manual);
      setViewerUrl(result.view_url);
    }
  }, [searchResults, currentMatchIdx, manuals]);

  // Highlight search terms in snippet
  const highlightSnippet = useCallback((text: string) => {
    if (!searchQuery || searchQuery.length < 2) return text;
    const regex = new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<mark class="bg-amber-200 dark:bg-amber-800 rounded px-0.5">$1</mark>');
  }, [searchQuery]);

  // ── Full-screen Viewer ─────────────────────────────────────────────
  if (viewMode === 'viewer' && viewingManual) {
    return (
      <div className="fixed inset-0 z-50 bg-black/90 flex flex-col">
        {/* Viewer header */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 text-white border-b border-slate-700">
          <div className="flex items-center gap-3 min-w-0">
            <BookOpen className="w-5 h-5 text-amber-400 flex-shrink-0" />
            <div className="min-w-0">
              <h2 className="text-sm font-semibold truncate">{viewingManual.title}</h2>
              <p className="text-xs text-slate-400">{viewingManual.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Search match navigation */}
            {searchResults.length > 0 && (
              <div className="flex items-center gap-1 mr-2 text-xs text-slate-400">
                <button
                  onClick={() => navigateMatch('prev')}
                  disabled={currentMatchIdx <= 0}
                  className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30 cursor-pointer disabled:cursor-default"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="px-1">
                  {currentMatchIdx + 1} / {searchResults.length} matches
                </span>
                <button
                  onClick={() => navigateMatch('next')}
                  disabled={currentMatchIdx >= searchResults.length - 1}
                  className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30 cursor-pointer disabled:cursor-default"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
            <a
              href={viewingManual.download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                bg-blue-600 text-white hover:bg-blue-700 transition-colors duration-150"
            >
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">Download</span>
            </a>
            <button
              onClick={closeViewer}
              className="p-2 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer"
              aria-label="Close viewer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Google Docs Viewer iframe */}
        <div className="flex-1 bg-slate-800">
          <iframe
            src={viewerUrl}
            className="w-full h-full border-0"
            title={viewingManual.title}
            sandbox="allow-scripts allow-same-origin allow-popups"
          />
        </div>
      </div>
    );
  }

  // ── Library View ───────────────────────────────────────────────────
  return (
    <div className="max-w-6xl mx-auto space-y-6 py-8 px-4">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-sm font-medium">
          <Library className="w-4 h-4" />
          Manuals Library
        </div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-50">
          Technical Manuals
        </h1>
        <p className="text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
          Browse, search, and view official Boeing-Stearman reference manuals.
          Search finds matches across all pages — click a result to jump directly to the page.
        </p>
      </div>

      {/* Search bar */}
      <div className="max-w-2xl mx-auto">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search inside manuals (part numbers, procedures, keywords...)"
            className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700
              bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm
              focus:ring-2 focus:ring-amber-500 focus:border-transparent outline-none
              placeholder:text-slate-400"
          />
          {searching && (
            <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
              <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
      </div>

      {/* Search results */}
      {searchResults.length > 0 && (
        <div className="max-w-4xl mx-auto space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
              {searchTotal} page{searchTotal !== 1 ? 's' : ''} match "{searchQuery}"
            </p>
          </div>
          <div className="space-y-2">
            {searchResults.map((result, idx) => (
              <button
                key={`${result.manual_id}-${result.page_number}`}
                onClick={() => { setCurrentMatchIdx(idx); openSearchResult(result); }}
                className="w-full text-left p-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700
                  hover:border-amber-300 dark:hover:border-amber-600 hover:shadow-md transition-all duration-200
                  cursor-pointer group"
              >
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-amber-50 dark:bg-amber-900/30 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileText className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                        {result.manual_title}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400">
                        Page {result.page_number}
                      </span>
                    </div>
                    <p
                      className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2"
                      dangerouslySetInnerHTML={{ __html: highlightSnippet(result.snippet) }}
                    />
                  </div>
                  <Eye className="w-4 h-4 text-slate-400 group-hover:text-amber-500 flex-shrink-0 mt-1" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* No search results message */}
      {searchQuery.length >= 2 && !searching && searchResults.length === 0 && (
        <div className="text-center py-8 text-slate-400 dark:text-slate-500">
          <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No matches found for "{searchQuery}"</p>
          <p className="text-xs mt-1">Try a different term or browse the manuals below</p>
        </div>
      )}

      {/* Category filter */}
      {categories.length > 1 && (
        <div className="flex items-center gap-2 justify-center">
          <Filter className="w-4 h-4 text-slate-400" />
          <button
            onClick={() => setActiveFilter(null)}
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors cursor-pointer ${
              !activeFilter
                ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveFilter(cat === activeFilter ? null : cat)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors cursor-pointer ${
                activeFilter === cat
                  ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Manual cards */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredManuals.map((manual) => (
            <div
              key={manual.id}
              className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden
                hover:shadow-lg transition-shadow duration-200"
            >
              {/* Card header with category badge */}
              <div className="px-6 pt-5 pb-3">
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 bg-red-50 dark:bg-red-900/30 rounded-xl flex items-center justify-center flex-shrink-0">
                    <FileText className="w-7 h-7 text-red-600 dark:text-red-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 font-medium">
                        {manual.category}
                      </span>
                      <span className="text-xs text-slate-400 dark:text-slate-500">
                        {manual.size_mb} MB
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 leading-snug">
                      {manual.title}
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5 line-clamp-2">
                      {manual.description}
                    </p>
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-3 px-6 py-4 border-t border-slate-100 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-850">
                <button
                  onClick={() => openViewer(manual)}
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

      {/* Footer */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4 space-y-1">
        <p>These manuals are U.S. government publications in the public domain.</p>
        <p>Have a manual to contribute? <a href="/submit" className="text-blue-500 hover:underline">Submit it here</a>.</p>
      </div>
    </div>
  );
}
