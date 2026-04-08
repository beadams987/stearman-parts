import { useEffect, useState, useMemo } from 'react';
import {
  Calendar, MapPin, ExternalLink, Filter, Plane, Clock, Globe,
} from 'lucide-react';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import apiClient from '../api/client.ts';

interface Event {
  id: number;
  title: string;
  description: string;
  event_type: string;
  start_date: string;
  end_date: string | null;
  location: string;
  city: string;
  state_province: string;
  country: string;
  venue: string;
  url: string;
  source: string;
  ai_summary: string;
  featured_aircraft: string[];
  image_url: string;
  status: string;
}

interface EventsResponse {
  events: Event[];
  total: number;
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  airshow: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
  'fly-in': 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300',
  museum: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300',
  formation: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300',
  restoration: 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300',
  gathering: 'bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300',
  other: 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300',
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateRange(start: string, end: string | null): string {
  if (!end || end === start) return formatDate(start);
  const s = new Date(start + 'T00:00:00');
  const e = new Date(end + 'T00:00:00');
  if (s.getMonth() === e.getMonth() && s.getFullYear() === e.getFullYear()) {
    return `${s.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}–${e.getDate()}, ${e.getFullYear()}`;
  }
  return `${formatDate(start)} – ${formatDate(end)}`;
}

export default function EventsPage() {
  const [data, setData] = useState<EventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState<string | null>(null);
  const [activeCountry, setActiveCountry] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'date' | 'location'>('date');

  usePageMeta(
    'Events',
    'Upcoming airshows, fly-ins, and events featuring Boeing-Stearman Kaydet biplanes worldwide.',
  );

  useEffect(() => {
    apiClient
      .get<EventsResponse>('/events', { params: { upcoming_only: true } })
      .then((res: { data: EventsResponse }) => setData(res.data))
      .catch(() => setData({ events: [], total: 0 }))
      .finally(() => setLoading(false));
  }, []);

  const events = data?.events ?? [];
  const eventTypes = useMemo(() => [...new Set(events.map((e) => e.event_type))].sort(), [events]);
  const countries = useMemo(() => [...new Set(events.map((e) => e.country).filter(Boolean))].sort(), [events]);

  const filtered = useMemo(() => {
    let result = events;
    if (activeType) result = result.filter((e) => e.event_type === activeType);
    if (activeCountry) result = result.filter((e) => e.country === activeCountry);
    if (sortBy === 'location') result = [...result].sort((a, b) => a.location.localeCompare(b.location));
    return result;
  }, [events, activeType, activeCountry, sortBy]);

  return (
    <div className="max-w-5xl mx-auto space-y-6 py-8 px-4">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm font-medium">
          <Calendar className="w-4 h-4" />
          {data ? `${data.total} Events` : 'Loading...'}
        </div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-50">
          Stearman Events
        </h1>
        <p className="text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
          Upcoming airshows, fly-ins, museum exhibits, and gatherings featuring
          Boeing-Stearman Kaydet biplanes around the world.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 justify-center">
        <Filter className="w-4 h-4 text-slate-400" />

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'date' | 'location')}
          className="px-3 py-1.5 text-xs rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-0 cursor-pointer"
        >
          <option value="date">Sort by Date</option>
          <option value="location">Sort by Location</option>
        </select>

        {/* Type filters */}
        <button
          onClick={() => setActiveType(null)}
          className={`px-3 py-1.5 text-xs font-medium rounded-full cursor-pointer transition-colors ${
            !activeType ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'}`}
        >
          All Types
        </button>
        {eventTypes.map((type) => (
          <button
            key={type}
            onClick={() => setActiveType(type === activeType ? null : type)}
            className={`px-3 py-1.5 text-xs font-medium rounded-full cursor-pointer capitalize transition-colors ${
              activeType === type ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'}`}
          >
            {type}
          </button>
        ))}

        {/* Country filter */}
        {countries.length > 1 && (
          <>
            <Globe className="w-3.5 h-3.5 text-slate-400 ml-2" />
            <select
              value={activeCountry || ''}
              onChange={(e) => setActiveCountry(e.target.value || null)}
              className="px-3 py-1.5 text-xs rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-0 cursor-pointer"
            >
              <option value="">All Countries</option>
              {countries.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </>
        )}
      </div>

      {/* Events list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <Plane className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto" />
          <h3 className="text-lg font-medium text-slate-600 dark:text-slate-400">
            No known events at this time
          </h3>
          <p className="text-sm text-slate-400 dark:text-slate-500 max-w-md mx-auto">
            {events.length === 0
              ? "We search for Stearman events worldwide every week. As these are fair-weather aircraft, events are typically concentrated in spring through fall. Check back soon!"
              : "No events match your current filters. Try adjusting the event type, country, or date range. Stearman events are seasonal — most fly-ins and airshows run April through October."}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((event) => (
            <a
              key={event.id}
              href={event.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700
                hover:shadow-lg hover:border-amber-300 dark:hover:border-amber-600 transition-all duration-200 overflow-hidden group"
            >
              <div className="p-5">
                <div className="flex items-start gap-4">
                  {/* Date badge */}
                  <div className="w-14 h-14 bg-amber-50 dark:bg-amber-900/30 rounded-xl flex flex-col items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-amber-700 dark:text-amber-300 uppercase">
                      {new Date(event.start_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short' })}
                    </span>
                    <span className="text-lg font-bold text-amber-800 dark:text-amber-200 leading-tight">
                      {new Date(event.start_date + 'T00:00:00').getDate()}
                    </span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 group-hover:text-amber-700 dark:group-hover:text-amber-400 transition-colors">
                          {event.title}
                          <ExternalLink className="w-3.5 h-3.5 inline ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </h3>
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium capitalize ${EVENT_TYPE_COLORS[event.event_type] || EVENT_TYPE_COLORS.other}`}>
                            {event.event_type}
                          </span>
                          <span className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                            <Clock className="w-3 h-3" />
                            {formatDateRange(event.start_date, event.end_date)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 mt-2 text-xs text-slate-500 dark:text-slate-400">
                      <MapPin className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate">{event.location}</span>
                      {event.venue && <span className="truncate">· {event.venue}</span>}
                    </div>

                    {(event.description || event.ai_summary) && (
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 line-clamp-2">
                        {event.description || event.ai_summary}
                      </p>
                    )}

                    {event.featured_aircraft.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {event.featured_aircraft.map((a) => (
                          <span key={a} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 flex items-center gap-0.5">
                            <Plane className="w-2.5 h-2.5" />{a}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4 space-y-1">
        <p>Events are discovered and updated weekly via AI search. Dates and details may change.</p>
        <p>Always verify with the event organizer before traveling. <a href="/submit" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:underline">Submit an event</a>.</p>
      </div>
    </div>
  );
}
