import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3, Users, Eye, Clock, TrendingDown, Globe,
  Smartphone, Monitor, Search as SearchIcon, Download, Info,
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend,
  CartesianGrid, BarChart, Bar,
} from 'recharts';
import apiClient from '../api/client.ts';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import { useDwellTime } from '../hooks/useAnalytics.ts';

interface AnalyticsSummary {
  total_visits: number;
  unique_visitors: number;
  total_pageviews: number;
  avg_session_duration_sec: number;
  bounce_rate_pct: number;
}

interface DailyVisit { date: string; visits: number; pageviews: number }
interface TopPage { path: string; views: number; avg_dwell_sec: number; avg_load_ms: number }
interface TopSearch { query: string; count: number }
interface TopDownload { filename: string; type: string; count: number }
interface ByCountry { country: string; visits: number }
interface ByDevice { device: string; pct: number }
interface ByBrowser { browser: string; pct: number }

interface AnalyticsResponse {
  period: string;
  generated_at: string;
  summary: AnalyticsSummary;
  daily_visits: DailyVisit[];
  top_pages: TopPage[];
  top_searches: TopSearch[];
  top_downloads: TopDownload[];
  by_country: ByCountry[];
  by_device: ByDevice[];
  by_browser: ByBrowser[];
  error?: string;
}

type RangeOption = 7 | 30 | 90;
const RANGE_LABELS: Record<RangeOption, string> = {
  7: '7 days',
  30: '30 days',
  90: '90 days',
};

function useAnalytics(days: RangeOption) {
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', days],
    queryFn: async () => {
      const res = await apiClient.get<AnalyticsResponse>('/analytics', { params: { days } });
      return res.data;
    },
    staleTime: 60 * 1000,
  });
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds < 1) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function formatNumber(n: number): string {
  return n.toLocaleString();
}

function KpiCard({
  icon: Icon, label, value, hint, accent,
}: {
  icon: typeof Users;
  label: string;
  value: string;
  hint?: string;
  accent: string;
}) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${accent}`}>
          <Icon className="w-5 h-5" />
        </div>
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          {label}
        </p>
      </div>
      <p className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-50">{value}</p>
      {hint && <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{hint}</p>}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 animate-pulse">
      <div className="h-6 w-24 bg-slate-200 dark:bg-slate-700 rounded mb-3" />
      <div className="h-8 w-16 bg-slate-200 dark:bg-slate-700 rounded" />
    </div>
  );
}

function TableCard<T>({
  title, icon: Icon, rows, columns, emptyMessage,
}: {
  title: string;
  icon: typeof Users;
  rows: T[];
  columns: { label: string; render: (row: T) => React.ReactNode; align?: 'left' | 'right' }[];
  emptyMessage: string;
}) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">
        <Icon className="w-4 h-4 text-amber-500" /> {title}
      </h2>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400 dark:text-slate-500 italic py-4 text-center">
          {emptyMessage}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
                {columns.map((c) => (
                  <th key={c.label}
                    className={`py-2 font-medium ${c.align === 'right' ? 'text-right' : 'text-left'}`}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}
                  className="border-b border-slate-100 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-900/50">
                  {columns.map((c) => (
                    <td key={c.label}
                      className={`py-2 text-slate-700 dark:text-slate-300 ${c.align === 'right' ? 'text-right font-mono' : ''}`}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="max-w-2xl mx-auto mt-10 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 text-center">
      <Info className="w-10 h-10 mx-auto text-amber-500 mb-3" />
      <h2 className="text-lg font-semibold text-amber-900 dark:text-amber-200 mb-2">
        No analytics data yet
      </h2>
      <p className="text-sm text-amber-800 dark:text-amber-300">
        Analytics will populate as visitors use the site. The Application Insights SDK was just
        installed — give it a few minutes after the first deployment, then refresh this page.
      </p>
    </div>
  );
}

export default function AnalyticsPage() {
  useDwellTime();
  usePageMeta(
    'Analytics',
    'Site usage dashboard — visits, top pages, top searches, geography, devices, browsers.',
  );

  const [days, setDays] = useState<RangeOption>(30);
  const { data, isLoading, error } = useAnalytics(days);

  const summary = data?.summary;
  const daily = data?.daily_visits ?? [];
  const topPages = data?.top_pages ?? [];
  const topSearches = data?.top_searches ?? [];
  const topDownloads = data?.top_downloads ?? [];
  const byCountry = data?.by_country ?? [];
  const byDevice = data?.by_device ?? [];
  const byBrowser = data?.by_browser ?? [];

  const hasAnyData =
    (summary?.total_pageviews ?? 0) > 0 ||
    daily.length > 0 ||
    topPages.length > 0 ||
    topSearches.length > 0;

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-amber-500" />
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
              StearmanHQ Analytics
            </h1>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Site usage overview · Public dashboard · Updated{' '}
            {data?.generated_at ? new Date(data.generated_at).toLocaleString() : '—'}
          </p>
        </div>

        {/* Range selector */}
        <div className="inline-flex rounded-lg border border-slate-300 dark:border-slate-600 overflow-hidden self-start">
          {(Object.keys(RANGE_LABELS) as unknown as RangeOption[]).map((d) => {
            const opt = Number(d) as RangeOption;
            const active = opt === days;
            return (
              <button
                key={opt}
                onClick={() => setDays(opt)}
                className={`px-3 py-1.5 text-xs font-medium cursor-pointer
                  ${active
                    ? 'bg-amber-600 text-white'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'}`}
              >
                {RANGE_LABELS[opt]}
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-300">
          Failed to load analytics data. Please try again later.
        </div>
      )}

      {/* KPI row */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {[0, 1, 2, 3, 4].map((i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <KpiCard icon={Users} label="Visits" value={formatNumber(summary?.total_visits ?? 0)}
            accent="bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400" />
          <KpiCard icon={Users} label="Unique Visitors" value={formatNumber(summary?.unique_visitors ?? 0)}
            accent="bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400" />
          <KpiCard icon={Eye} label="Page Views" value={formatNumber(summary?.total_pageviews ?? 0)}
            accent="bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400" />
          <KpiCard icon={Clock} label="Avg Session" value={formatDuration(summary?.avg_session_duration_sec ?? 0)}
            accent="bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400" />
          <KpiCard icon={TrendingDown} label="Bounce Rate"
            value={`${(summary?.bounce_rate_pct ?? 0).toFixed(1)}%`}
            accent="bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400" />
        </div>
      )}

      {!isLoading && !hasAnyData && <EmptyState />}

      {/* Daily visits chart */}
      {!isLoading && hasAnyData && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">
            <BarChart3 className="w-4 h-4 text-amber-500" /> Daily traffic
          </h2>
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <LineChart data={daily} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.25} />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgb(30 41 59)',
                    border: '1px solid rgb(51 65 85)',
                    borderRadius: 8,
                    fontSize: 12,
                    color: '#e2e8f0',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="visits" stroke="#d97706" strokeWidth={2} dot={false} name="Visits" />
                <Line type="monotone" dataKey="pageviews" stroke="#2563eb" strokeWidth={2} dot={false} name="Page Views" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Two-column: Top pages / Countries */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TableCard
          title="Top pages"
          icon={Eye}
          rows={topPages}
          emptyMessage="No page view data yet."
          columns={[
            {
              label: 'Path',
              render: (r) => <span className="font-mono text-slate-800 dark:text-slate-100">{r.path || '/'}</span>,
            },
            { label: 'Views', align: 'right', render: (r) => formatNumber(r.views) },
            { label: 'Avg dwell', align: 'right', render: (r) => formatDuration(r.avg_dwell_sec) },
            { label: 'Load (ms)', align: 'right', render: (r) => (r.avg_load_ms > 0 ? Math.round(r.avg_load_ms) : '—') },
          ]}
        />
        <TableCard
          title="By country"
          icon={Globe}
          rows={byCountry}
          emptyMessage="No geographic data yet."
          columns={[
            { label: 'Country', render: (r) => r.country },
            { label: 'Visits', align: 'right', render: (r) => formatNumber(r.visits) },
          ]}
        />
      </div>

      {/* Two-column: Top searches / Top downloads */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TableCard
          title="Top searches"
          icon={SearchIcon}
          rows={topSearches}
          emptyMessage="No searches recorded yet."
          columns={[
            {
              label: 'Query',
              render: (r) => <span className="font-mono">{r.query}</span>,
            },
            { label: 'Count', align: 'right', render: (r) => formatNumber(r.count) },
          ]}
        />
        <TableCard
          title="Top downloads"
          icon={Download}
          rows={topDownloads}
          emptyMessage="No downloads recorded yet."
          columns={[
            {
              label: 'File',
              render: (r) => <span className="font-mono text-xs truncate block max-w-[220px]">{r.filename}</span>,
            },
            { label: 'Type', render: (r) => r.type || '—' },
            { label: 'Count', align: 'right', render: (r) => formatNumber(r.count) },
          ]}
        />
      </div>

      {/* Device + Browser breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">
            <Smartphone className="w-4 h-4 text-amber-500" /> Device type
          </h2>
          {byDevice.length === 0 ? (
            <p className="text-xs text-slate-400 italic py-4 text-center">No device data yet.</p>
          ) : (
            <div style={{ width: '100%', height: 220 }}>
              <ResponsiveContainer>
                <BarChart data={byDevice} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.25} />
                  <XAxis dataKey="device" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} unit="%" />
                  <Tooltip
                    formatter={(v) => `${v}%`}
                    contentStyle={{
                      backgroundColor: 'rgb(30 41 59)',
                      border: '1px solid rgb(51 65 85)',
                      borderRadius: 8,
                      fontSize: 12,
                      color: '#e2e8f0',
                    }}
                  />
                  <Bar dataKey="pct" fill="#d97706" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">
            <Monitor className="w-4 h-4 text-amber-500" /> Browser
          </h2>
          {byBrowser.length === 0 ? (
            <p className="text-xs text-slate-400 italic py-4 text-center">No browser data yet.</p>
          ) : (
            <div style={{ width: '100%', height: 220 }}>
              <ResponsiveContainer>
                <BarChart data={byBrowser} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.25} />
                  <XAxis dataKey="browser" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} unit="%" />
                  <Tooltip
                    formatter={(v) => `${v}%`}
                    contentStyle={{
                      backgroundColor: 'rgb(30 41 59)',
                      border: '1px solid rgb(51 65 85)',
                      borderRadius: 8,
                      fontSize: 12,
                      color: '#e2e8f0',
                    }}
                  />
                  <Bar dataKey="pct" fill="#2563eb" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {data?.error && (
        <p className="text-xs text-slate-400 dark:text-slate-500 text-center italic">
          {data.error}
        </p>
      )}

      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4">
        <p>Data source: Azure Application Insights · Aggregates only, no individual events exposed.</p>
      </div>
    </div>
  );
}
