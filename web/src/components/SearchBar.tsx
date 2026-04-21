import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useSearchSuggest } from '../api/hooks.ts';
import { trackSearch } from '../hooks/useAnalytics.ts';

interface SearchBarProps {
  compact?: boolean;
}

type SearchType = 'all' | 'drawing_number' | 'keyword';

export default function SearchBar({ compact = false }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<SearchType>('all');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { data: suggestions } = useSearchSuggest(query);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (query.trim().length < 2) return;
      trackSearch(query, searchType);
      const params = new URLSearchParams({ q: query.trim() });
      if (searchType !== 'all') {
        params.set('type', searchType);
      }
      navigate(`/search?${params.toString()}`);
      setShowSuggestions(false);
    },
    [query, searchType, navigate],
  );

  const handleSuggestionClick = useCallback(
    (value: string, type: 'drawing_number' | 'keyword') => {
      setQuery(value);
      setSearchType(type);
      setShowSuggestions(false);
      trackSearch(value, `${type}_suggestion`);
      const params = new URLSearchParams({ q: value, type });
      navigate(`/search?${params.toString()}`);
    },
    [navigate],
  );

  const handleClear = useCallback(() => {
    setQuery('');
    inputRef.current?.focus();
    setShowSuggestions(false);
  }, []);

  // Close suggestions on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className={`relative ${compact ? 'w-full' : 'w-full max-w-2xl'}`}>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setShowSuggestions(true);
            }}
            onFocus={() => query.length >= 2 && setShowSuggestions(true)}
            placeholder="Search drawings, part numbers, keywords..."
            className={`w-full pl-9 pr-8 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600
              rounded-lg text-sm text-slate-800 dark:text-slate-200 placeholder:text-slate-400
              focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500
              ${compact ? 'py-2' : 'py-2.5'}`}
          />
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Search type filter */}
        {!compact && (
          <div className="flex rounded-lg border border-slate-300 dark:border-slate-600 overflow-hidden">
            {(
              [
                { value: 'all', label: 'All' },
                { value: 'drawing_number', label: 'Drawing #' },
                { value: 'keyword', label: 'Key Word' },
              ] as const
            ).map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => setSearchType(value)}
                className={`px-3 py-2 text-xs font-medium whitespace-nowrap cursor-pointer
                  ${
                    searchType === value
                      ? 'bg-amber-600 text-white'
                      : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
                  }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        <button
          type="submit"
          className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium
            transition-colors duration-150 cursor-pointer whitespace-nowrap"
        >
          Search
        </button>
      </form>

      {/* Suggestions dropdown */}
      {showSuggestions && suggestions && suggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto">
          {suggestions.map((suggestion, index) => (
            <button
              key={`${suggestion.value}-${index}`}
              onClick={() => handleSuggestionClick(suggestion.value, suggestion.type)}
              className="w-full px-4 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-slate-700
                flex items-center gap-3 text-sm cursor-pointer border-b border-slate-100 dark:border-slate-700 last:border-0"
            >
              <Search className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
              <span className="text-slate-800 dark:text-slate-200 truncate">
                {suggestion.value}
              </span>
              <span className="ml-auto text-xs text-slate-400 dark:text-slate-500 flex-shrink-0 font-mono">
                {suggestion.type === 'drawing_number' ? 'DWG#' : 'KW'}
              </span>
              <span className="text-xs text-slate-400 dark:text-slate-500 flex-shrink-0">
                ({suggestion.count})
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
