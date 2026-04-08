import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  FileText, Download, BookOpen, Eye, X, Search,
  Filter, ChevronLeft, ChevronRight, Library, Plane,
} from 'lucide-react';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import apiClient from '../api/client.ts';
import PdfViewer from '../components/PdfViewer.tsx';

interface CatalogItem {
  id: string;
  title: string;
  description: string;
  category: string;
  subcategory: string;
  content_type: string;
  size_mb: number;
  tags: string[];
  source: string;
  year: number | null;
  models: string[];
  download_url: string;
}

interface CatalogResponse {
  items: CatalogItem[];
  total: number;
  categories: string[];
}

interface ManualPageResult {
  manual_id: string;
  manual_title: string;
  page_number: number;
  snippet: string;
}

interface ManualSearchResponse {
  results: ManualPageResult[];
  total: number;
  query: string;
}

export default function ManualsPage() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewingItem, setViewingItem] = useState<CatalogItem | null>(null);

  // Filters
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ManualPageResult[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searching, setSearching] = useState(false);
  const [currentMatchIdx, setCurrentMatchIdx] = useState(0);

  usePageMeta(
    'Manuals Library',
    'Browse and search the complete Boeing-Stearman technical manual library — 36+ documents covering maintenance, parts, pilot handbooks, training, and more.',
  );

  // Load catalog
  useEffect(() => {
    apiClient
      .get<CatalogResponse>('/manuals')
      .then((res: { data: CatalogResponse }) => setCatalog(res.data))
      .catch(() => setCatalog({ items: [], total: 0, categories: [] }))
      .finally(() => setLoading(false));
  }, []);

  // Debounced page-level search
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
        .catch(() => { setSearchResults([]); setSearchTotal(0); })
        .finally(() => setSearching(false));
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Derived data
  const items = catalog?.items ?? [];
  const categories = catalog?.categories ?? [];
  const allModels = useMemo(() => [...new Set(items.flatMap((i) => i.models))].sort(), [items]);

  const filteredItems = useMemo(() => {
    let result = items;
    if (activeCategory) result = result.filter((i) => i.category === activeCategory);
    if (activeModel) result = result.filter((i) => i.models.includes(activeModel));
    // Also filter by search query on title/description (catalog-level)
    if (searchQuery.length >= 2) {
      const q = searchQuery.toLowerCase();
      result = result.filter((i) =>
        i.title.toLowerCase().includes(q) ||
        i.description.toLowerCase().includes(q) ||
        i.tags.some((t) => t.toLowerCase().includes(q)),
      );
    }
    return result;
  }, [items, activeCategory, activeModel, searchQuery]);

  // Group by category
  const grouped = useMemo(() => {
    const groups: Record<string, CatalogItem[]> = {};
    for (const item of filteredItems) {
      (groups[item.category] ??= []).push(item);
    }
    return groups;
  }, [filteredItems]);

  const openViewer = useCallback((item: CatalogItem) => {
    setViewingItem(item);
  }, []);

  const openSearchResult = useCallback((result: ManualPageResult, idx: number) => {
    setCurrentMatchIdx(idx);
    const item = items.find((i) =>
      i.id === result.manual_id ||
      result.manual_id.includes(i.id),
    );
    if (item) openViewer(item);
  }, [items, openViewer]);

  const navigateMatch = useCallback((dir: 'prev' | 'next') => {
    if (searchResults.length === 0) return;
    const newIdx = dir === 'next'
      ? Math.min(currentMatchIdx + 1, searchResults.length - 1)
      : Math.max(currentMatchIdx - 1, 0);
    setCurrentMatchIdx(newIdx);
    const r = searchResults[newIdx];
    const item = items.find((i) => i.id === r.manual_id || r.manual_id.includes(i.id));
    if (item) { setViewingItem(item); }
  }, [searchResults, currentMatchIdx, items]);

  const highlightSnippet = useCallback((text: string) => {
    if (searchQuery.length < 2) return text;
    const re = new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(re, '<mark class="bg-amber-200 dark:bg-amber-800 rounded px-0.5">$1</mark>');
  }, [searchQuery]);

  // ── Viewer ─────────────────────────────────────────────────────────
  if (viewingItem) {
    return (
      <div className="fixed inset-0 z-50 bg-black/90 flex flex-col">
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 text-white border-b border-slate-700">
          <div className="flex items-center gap-3 min-w-0">
            <BookOpen className="w-5 h-5 text-amber-400 flex-shrink-0" />
            <div className="min-w-0">
              <h2 className="text-sm font-semibold truncate">{viewingItem.title}</h2>
              <p className="text-xs text-slate-400 truncate">{viewingItem.category} · {viewingItem.source}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {searchResults.length > 0 && (
              <div className="flex items-center gap-1 mr-2 text-xs text-slate-400">
                <button onClick={() => navigateMatch('prev')} disabled={currentMatchIdx <= 0}
                  className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30 cursor-pointer disabled:cursor-default">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="px-1">{currentMatchIdx + 1} / {searchResults.length}</span>
                <button onClick={() => navigateMatch('next')} disabled={currentMatchIdx >= searchResults.length - 1}
                  className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30 cursor-pointer disabled:cursor-default">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
            <a href={viewingItem.download_url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700">
              <Download className="w-4 h-4" /><span className="hidden sm:inline">Download</span>
            </a>
            <button onClick={() => setViewingItem(null)}
              className="p-2 rounded-lg hover:bg-slate-700 cursor-pointer" aria-label="Close">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        <PdfViewer url={viewingItem.download_url} />
      </div>
    );
  }

  // ── Library ────────────────────────────────────────────────────────
  return (
    <div className="max-w-6xl mx-auto space-y-6 py-8 px-4">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-sm font-medium">
          <Library className="w-4 h-4" />
          {catalog ? `${catalog.total} Documents` : 'Loading...'}
        </div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-50">Manuals Library</h1>
        <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          The complete Boeing-Stearman technical reference — maintenance manuals, parts catalogs,
          pilot handbooks, training documents, regulatory data, and safety reports.
          Search finds matches across all pages.
        </p>
      </div>

      {/* Search */}
      <div className="max-w-2xl mx-auto">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search inside manuals (part numbers, procedures, keywords...)"
            className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700
              bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm
              focus:ring-2 focus:ring-amber-500 focus:border-transparent outline-none" />
          {searching && (
            <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
              <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
      </div>

      {/* Page-level search results */}
      {searchResults.length > 0 && (
        <div className="max-w-4xl mx-auto space-y-2">
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
            {searchTotal} page{searchTotal !== 1 ? 's' : ''} match "{searchQuery}" — click to view
          </p>
          {searchResults.slice(0, 10).map((r, idx) => (
            <button key={`${r.manual_id}-${r.page_number}`}
              onClick={() => openSearchResult(r, idx)}
              className="w-full text-left p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700
                hover:border-amber-300 dark:hover:border-amber-600 hover:shadow-md transition-all cursor-pointer group">
              <div className="flex items-start gap-3">
                <FileText className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200">{r.manual_title}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-500">p.{r.page_number}</span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2"
                    dangerouslySetInnerHTML={{ __html: highlightSnippet(r.snippet) }} />
                </div>
                <Eye className="w-4 h-4 text-slate-400 group-hover:text-amber-500 flex-shrink-0" />
              </div>
            </button>
          ))}
          {searchTotal > 10 && (
            <p className="text-xs text-slate-400 text-center">Showing first 10 of {searchTotal} matches</p>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 justify-center">
        <button onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full
            bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 cursor-pointer">
          <Filter className="w-3.5 h-3.5" /> Filters {(activeCategory || activeModel) ? '●' : ''}
        </button>

        {/* Category pills — always visible */}
        <button onClick={() => setActiveCategory(null)}
          className={`px-3 py-1.5 text-xs font-medium rounded-full cursor-pointer transition-colors ${
            !activeCategory ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'}`}>
          All ({items.length})
        </button>
        {categories.map((cat) => {
          const count = items.filter((i) => i.category === cat).length;
          return (
            <button key={cat} onClick={() => setActiveCategory(cat === activeCategory ? null : cat)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full cursor-pointer transition-colors ${
                activeCategory === cat ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'}`}>
              {cat} ({count})
            </button>
          );
        })}
      </div>

      {/* Model filter (expanded) */}
      {showFilters && allModels.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 justify-center">
          <Plane className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-xs text-slate-500">Model:</span>
          <button onClick={() => setActiveModel(null)}
            className={`px-2.5 py-1 text-xs rounded-full cursor-pointer ${
              !activeModel ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-slate-200'}`}>
            All
          </button>
          {allModels.map((m) => (
            <button key={m} onClick={() => setActiveModel(m === activeModel ? null : m)}
              className={`px-2.5 py-1 text-xs rounded-full cursor-pointer ${
                activeModel === m ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-slate-200'}`}>
              {m}
            </button>
          ))}
        </div>
      )}

      {/* Content — grouped by category */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(grouped).map(([category, categoryItems]) => (
            <div key={category}>
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-3 flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-amber-500" />
                {category}
                <span className="text-xs font-normal text-slate-400 ml-1">({categoryItems.length})</span>
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {categoryItems.map((item) => (
                  <div key={item.id}
                    className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden hover:shadow-lg transition-shadow">
                    <div className="p-5">
                      <div className="flex items-start gap-3">
                        <div className="w-11 h-11 bg-red-50 dark:bg-red-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                          <FileText className="w-5 h-5 text-red-600 dark:text-red-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 leading-snug">
                            {item.title}
                          </h3>
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                            {item.description}
                          </p>
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {item.models.map((m) => (
                              <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium">
                                {m}
                              </span>
                            ))}
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-500">
                              {item.size_mb < 1 ? '<1' : Math.round(item.size_mb)} MB
                            </span>
                            {item.source && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-400 truncate max-w-[150px]">
                                {item.source}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 px-5 py-3 border-t border-slate-100 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900/30">
                      <button onClick={() => openViewer(item)}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg
                          border border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400
                          hover:bg-blue-50 dark:hover:bg-blue-900/20 cursor-pointer">
                        <Eye className="w-3.5 h-3.5" /> View
                      </button>
                      <a href={item.download_url} target="_blank" rel="noopener noreferrer"
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg
                          bg-blue-600 text-white hover:bg-blue-700">
                        <Download className="w-3.5 h-3.5" /> Download
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4 space-y-1">
        <p>Public domain documents sourced from stearman-aero.com, FAA, NTSB, Internet Archive, and community contributors.</p>
        <p>Have a manual to contribute? <a href="/submit" className="text-blue-500 hover:underline">Submit it here</a>.</p>
      </div>
    </div>
  );
}
