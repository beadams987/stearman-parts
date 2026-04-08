import { useState, useMemo } from 'react';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { Search, Layers, Image as ImageIcon, Filter, X } from 'lucide-react';
import { useSearch, useFolders } from '../api/hooks.ts';
import type { SearchResult } from '../types.ts';

function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  const parts = text.split(regex);
  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="bg-yellow-200 dark:bg-yellow-800/60 text-inherit rounded px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

function ResultCard({ result, query }: { result: SearchResult; query: string }) {
  const navigate = useNavigate();
  const [imgError, setImgError] = useState(false);

  const handleClick = () => {
    if (result.type === 'bundle') {
      navigate(`/bundles/${result.id}`);
    } else {
      navigate(`/images/${result.id}`);
    }
  };

  return (
    <button
      onClick={handleClick}
      className="flex gap-4 p-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700
        hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md transition-all duration-200
        text-left w-full cursor-pointer group"
    >
      {/* Thumbnail */}
      <div className="w-20 h-20 flex-shrink-0 rounded-md overflow-hidden bg-slate-100 dark:bg-slate-900">
        {!imgError ? (
          <img
            src={result.thumbnail_url}
            alt={result.file_name}
            loading="lazy"
            onError={() => setImgError(true)}
            className="w-full h-full object-contain p-1"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400">
            <ImageIcon className="w-6 h-6" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
            {result.file_name}
          </p>
          {result.type === 'bundle' && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded font-medium flex-shrink-0">
              <Layers className="w-3 h-3" />
              {result.page_count} pages
            </span>
          )}
        </div>

        {/* Matched value */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 dark:text-slate-500 font-mono uppercase flex-shrink-0">
            {result.matched_field === 'drawing_number' ? 'DWG#' : result.matched_field === 'ocr_text' ? 'OCR' : 'KW'}:
          </span>
          <span className="text-sm text-blue-600 dark:text-blue-400 font-mono truncate">
            <HighlightMatch text={result.matched_value} query={query} />
          </span>
        </div>

        {/* OCR snippet */}
        {result.ocr_snippet && (
          <p className="text-xs text-slate-500 dark:text-slate-400 italic line-clamp-2">
            <HighlightMatch text={result.ocr_snippet} query={query} />
          </p>
        )}

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5">
          {result.drawing_numbers.map((dn) => (
            <span
              key={dn}
              className="text-xs font-mono px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded"
            >
              {dn}
            </span>
          ))}
          {result.keywords.slice(0, 3).map((kw) => (
            <span
              key={kw}
              className="text-xs px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded"
            >
              {kw}
            </span>
          ))}
          {result.keywords.length > 3 && (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              +{result.keywords.length - 3} more
            </span>
          )}
        </div>

        {/* Folder */}
        <p className="text-xs text-slate-400 dark:text-slate-500">
          {result.folder_name}
        </p>
      </div>
    </button>
  );
}

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get('q') ?? '';
  const type = searchParams.get('type') as 'drawing_number' | 'keyword' | 'ocr' | undefined;
  const folderIdParam = searchParams.get('folder_id');
  const folderId = folderIdParam ? Number(folderIdParam) : undefined;
  const pageParam = searchParams.get('page');
  const page = pageParam ? Number(pageParam) : 1;

  usePageMeta(
    query ? `Search: ${query}` : 'Search',
    'Search Stearman engineering drawings by drawing number, keyword, or full text.',
  );

  const [showFilters, setShowFilters] = useState(false);

  const { data: searchData, isLoading } = useSearch(query, type, folderId, page);
  const { data: folders } = useFolders();

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (type) count++;
    if (folderId) count++;
    return count;
  }, [type, folderId]);

  const setFilterParam = (key: string, value: string | undefined) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.set('page', '1'); // Reset to page 1 on filter change
    setSearchParams(params);
  };

  const setPageParam = (newPage: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', String(newPage));
    setSearchParams(params);
  };

  if (!query) {
    return (
      <div className="text-center py-16 space-y-4">
        <Search className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-600" />
        <p className="text-lg text-slate-500 dark:text-slate-400">
          Enter a search query to find drawings.
        </p>
        <Link
          to="/"
          className="inline-block text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          Back to Home
        </Link>
      </div>
    );
  }

  return (
    <div className="flex gap-6 p-4 min-h-[500px]">
      {/* Filters sidebar - desktop */}
      <aside
        className={`w-56 flex-shrink-0 space-y-4 ${showFilters ? 'block' : 'hidden'} lg:block`}
      >
        <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4 space-y-4">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            Filters
          </h3>

          {/* Search type */}
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400 font-medium block mb-2">
              Search Type
            </label>
            <div className="space-y-1.5">
              {[
                { value: undefined, label: 'All' },
                { value: 'drawing_number', label: 'Drawing #' },
                { value: 'keyword', label: 'Key Word' },
                { value: 'ocr', label: 'Full Text (OCR)' },
              ].map(({ value, label }) => (
                <button
                  key={label}
                  onClick={() => setFilterParam('type', value)}
                  className={`w-full text-left px-3 py-1.5 text-sm rounded-md cursor-pointer
                    ${
                      type === value
                        ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Folder filter */}
          {folders && folders.length > 0 && (
            <div>
              <label className="text-xs text-slate-500 dark:text-slate-400 font-medium block mb-2">
                Folder
              </label>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                <button
                  onClick={() => setFilterParam('folder_id', undefined)}
                  className={`w-full text-left px-3 py-1.5 text-sm rounded-md cursor-pointer
                    ${
                      !folderId
                        ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
                    }`}
                >
                  All Folders
                </button>
                {folders.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFilterParam('folder_id', String(f.id))}
                    className={`w-full text-left px-3 py-1.5 text-xs rounded-md truncate cursor-pointer
                      ${
                        folderId === f.id
                          ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
                      }`}
                  >
                    {f.folder_name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Results */}
      <div className="flex-1 min-w-0 space-y-4">
        {/* Results header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-slate-800 dark:text-slate-200">
              Search Results
            </h1>
            {searchData && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {searchData.total} results for &ldquo;{searchData.query}&rdquo;
                {searchData.total_pages > 1 && ` (page ${searchData.page} of ${searchData.total_pages})`}
              </p>
            )}
          </div>

          {/* Mobile filter toggle */}
          <button
            onClick={() => setShowFilters((v) => !v)}
            className="lg:hidden flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md
              bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600
              text-slate-700 dark:text-slate-300 cursor-pointer"
          >
            <Filter className="w-4 h-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>

        {/* Active filter pills */}
        {activeFilterCount > 0 && (
          <div className="flex flex-wrap gap-2">
            {type && (
              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-md">
                {type === 'drawing_number' ? 'Drawing #' : type === 'ocr' ? 'Full Text (OCR)' : 'Key Word'}
                <button
                  onClick={() => setFilterParam('type', undefined)}
                  className="hover:text-blue-900 dark:hover:text-blue-100 cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
            {folderId && folders && (
              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-md">
                {folders.find((f) => f.id === folderId)?.folder_name ?? `Folder ${folderId}`}
                <button
                  onClick={() => setFilterParam('folder_id', undefined)}
                  className="hover:text-blue-900 dark:hover:text-blue-100 cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton h-24 rounded-lg" />
            ))}
          </div>
        )}

        {/* Results list */}
        {!isLoading && searchData && (
          <div className="space-y-3">
            {searchData.results.length === 0 ? (
              <div className="text-center py-12">
                <Search className="w-10 h-10 mx-auto text-slate-300 dark:text-slate-600 mb-3" />
                <p className="text-slate-500 dark:text-slate-400">
                  No results found for &ldquo;{query}&rdquo;.
                </p>
                <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
                  Try a different search term or adjust your filters.
                </p>
              </div>
            ) : (
              searchData.results.map((result) => (
                <ResultCard key={`${result.type}-${result.id}`} result={result} query={query} />
              ))
            )}
          </div>
        )}

        {/* Pagination */}
        {searchData && searchData.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2 pt-4">
            <button
              onClick={() => setPageParam(Math.max(1, page - 1))}
              disabled={page === 1}
              className="px-4 py-2 text-sm rounded-md bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600
                text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700
                disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              Previous
            </button>
            <span className="text-sm text-slate-600 dark:text-slate-400">
              Page {page} of {searchData.total_pages}
            </span>
            <button
              onClick={() => setPageParam(Math.min(searchData.total_pages, page + 1))}
              disabled={page === searchData.total_pages}
              className="px-4 py-2 text-sm rounded-md bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600
                text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700
                disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
