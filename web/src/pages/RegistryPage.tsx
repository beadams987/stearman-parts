import { useEffect, useState } from 'react';
import { Search, MapPin, Plane, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import apiClient from '../api/client.ts';

interface RegistryEntry {
  n_number: string;
  serial_number: string;
  manufacturer: string;
  model: string;
  year_mfr: string;
  owner_name: string;
  city: string;
  state: string;
  country: string;
}

interface RegistryResponse {
  entries: RegistryEntry[];
  total: number;
  states: string[];
  models: string[];
}

export default function RegistryPage() {
  const [data, setData] = useState<RegistryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 50;

  usePageMeta(
    'Owner Directory',
    'FAA-registered Boeing-Stearman Kaydet aircraft directory. Find Stearman owners by N-number, state, model, or name.',
  );

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (search) params.q = search;
    if (stateFilter) params.state = stateFilter;
    if (modelFilter) params.model = modelFilter;

    apiClient
      .get<RegistryResponse>('/registry', { params })
      .then((res: { data: RegistryResponse }) => setData(res.data))
      .catch(() => setData({ entries: [], total: 0, states: [], models: [] }))
      .finally(() => setLoading(false));
  }, [search, stateFilter, modelFilter, page]);

  // Debounce search
  const [searchInput, setSearchInput] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [search, stateFilter, modelFilter]);

  const totalPages = Math.ceil((data?.total ?? 0) / pageSize);

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-8 px-4">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 text-sm font-medium">
          <Plane className="w-4 h-4" />
          {data ? `${data.total.toLocaleString()} Registered Aircraft` : 'Loading...'}
        </div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-50">
          Stearman Owner Directory
        </h1>
        <p className="text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
          FAA-registered Boeing-Stearman aircraft across the United States.
          Search by N-number, owner name, city, state, or model.
        </p>
      </div>

      {/* Search + Filters */}
      <div className="max-w-3xl mx-auto space-y-3">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by N-number, owner name, or city..."
            className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700
              bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-sm
              focus:ring-2 focus:ring-amber-500 focus:border-transparent outline-none"
          />
        </div>

        <div className="flex flex-wrap gap-2 justify-center">
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-0 cursor-pointer"
          >
            <option value="">All States</option>
            {(data?.states ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>

          <select
            value={modelFilter}
            onChange={(e) => setModelFilter(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-0 cursor-pointer"
          >
            <option value="">All Models</option>
            {(data?.models ?? []).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>

          {(stateFilter || modelFilter || search) && (
            <button
              onClick={() => { setStateFilter(''); setModelFilter(''); setSearchInput(''); setSearch(''); }}
              className="px-3 py-1.5 text-xs rounded-full bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 cursor-pointer"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Results table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                <th className="pb-3 font-semibold text-slate-600 dark:text-slate-400">N-Number</th>
                <th className="pb-3 font-semibold text-slate-600 dark:text-slate-400">Model</th>
                <th className="pb-3 font-semibold text-slate-600 dark:text-slate-400 hidden sm:table-cell">Owner</th>
                <th className="pb-3 font-semibold text-slate-600 dark:text-slate-400">Location</th>
                <th className="pb-3 font-semibold text-slate-600 dark:text-slate-400 hidden md:table-cell">S/N</th>
                <th className="pb-3 font-semibold text-slate-600 dark:text-slate-400 hidden md:table-cell">Year</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {(data?.entries ?? []).map((entry) => (
                <tr key={entry.n_number} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="py-3">
                    <a
                      href={`https://registry.faa.gov/AircraftInquiry/Search/NNumberResult?nNumberTxt=${entry.n_number.replace('N', '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono font-semibold text-amber-700 dark:text-amber-400 hover:underline flex items-center gap-1"
                    >
                      {entry.n_number}
                      <ExternalLink className="w-3 h-3 opacity-50" />
                    </a>
                  </td>
                  <td className="py-3 text-slate-700 dark:text-slate-300 text-xs">{entry.model}</td>
                  <td className="py-3 text-slate-600 dark:text-slate-400 hidden sm:table-cell truncate max-w-[200px]">{entry.owner_name}</td>
                  <td className="py-3 text-slate-500 dark:text-slate-400 text-xs">
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {entry.city}{entry.state ? `, ${entry.state}` : ''}
                    </span>
                  </td>
                  <td className="py-3 text-slate-400 font-mono text-xs hidden md:table-cell">{entry.serial_number}</td>
                  <td className="py-3 text-slate-400 text-xs hidden md:table-cell">{entry.year_mfr}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 disabled:opacity-30 cursor-pointer disabled:cursor-default"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-slate-500 dark:text-slate-400">
            Page {page} of {totalPages} ({data?.total.toLocaleString()} aircraft)
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 disabled:opacity-30 cursor-pointer disabled:cursor-default"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Footer */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4 space-y-1">
        <p>Source: <a href="https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/releasable_aircraft_download" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:underline">FAA Releasable Aircraft Database</a>. Updated weekly.</p>
        <p>N-number links open the FAA registry in a new tab. Owner information is public record per 49 U.S.C. § 44103.</p>
      </div>
    </div>
  );
}
