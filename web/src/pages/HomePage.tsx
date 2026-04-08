import { useNavigate } from 'react-router-dom';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import { useEffect, useState } from 'react';
import {
  Image as ImageIcon,
  Search,
  ArrowRight,
  BookOpen,
  Upload,
  Calendar,
  MapPin,
  Clock,
  ExternalLink,
} from 'lucide-react';
import { useStats } from '../api/hooks.ts';
import apiClient from '../api/client.ts';
import SearchBar from '../components/SearchBar.tsx';

interface QuickCardProps {
  icon: typeof ImageIcon;
  title: string;
  stat: string;
  description: string;
  color: string;
  hoverBorder: string;
  onClick: () => void;
}

function QuickCard({ icon: Icon, title, stat, description, color, hoverBorder, onClick }: QuickCardProps) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-start gap-3 p-5 sm:p-6 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700
        ${hoverBorder} hover:shadow-lg transition-all duration-200 text-left group cursor-pointer w-full`}
    >
      <div className={`w-12 h-12 ${color} rounded-xl flex items-center justify-center flex-shrink-0`}>
        <Icon className="w-6 h-6" />
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">
            {title}
          </h3>
          <ArrowRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
        </div>
        <p className="text-2xl font-bold text-slate-900 dark:text-slate-50">{stat}</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
      </div>
    </button>
  );
}

interface EventPreview {
  id: number;
  title: string;
  start_date: string;
  end_date: string | null;
  location: string;
  event_type: string;
  url: string;
}

function UpcomingEvents() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<EventPreview[]>([]);

  useEffect(() => {
    apiClient
      .get<{ events: EventPreview[] }>('/events', { params: { upcoming_only: true, page_size: 4 } })
      .then((res: { data: { events: EventPreview[] } }) => setEvents(res.data.events.slice(0, 4)))
      .catch(() => setEvents([]));
  }, []);

  if (events.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <Calendar className="w-5 h-5 text-red-500" />
          Upcoming Events
        </h2>
        <button
          onClick={() => navigate('/events')}
          className="text-sm text-amber-700 dark:text-amber-400 hover:underline flex items-center gap-1 cursor-pointer"
        >
          View all events <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {events.map((event) => (
          <a
            key={event.id}
            href={event.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-3 p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700
              hover:border-amber-300 dark:hover:border-amber-600 hover:shadow-md transition-all duration-200 group no-underline"
          >
            <div className="w-12 h-12 bg-red-50 dark:bg-red-900/30 rounded-xl flex flex-col items-center justify-center flex-shrink-0">
              <span className="text-[10px] font-bold text-red-600 dark:text-red-400 uppercase leading-tight">
                {new Date(event.start_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short' })}
              </span>
              <span className="text-base font-bold text-red-700 dark:text-red-300 leading-tight">
                {new Date(event.start_date + 'T00:00:00').getDate()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate group-hover:text-amber-700 dark:group-hover:text-amber-400 transition-colors">
                {event.title}
                <ExternalLink className="w-3 h-3 inline ml-1 opacity-0 group-hover:opacity-100" />
              </h3>
              <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 dark:text-slate-400">
                <span className="flex items-center gap-1 truncate">
                  <MapPin className="w-3 h-3 flex-shrink-0" />
                  {event.location}
                </span>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const { data: stats } = useStats();


  usePageMeta(
    'Home',
    'The Boeing-Stearman Information Hub — 7,673 engineering drawings, 36+ technical manuals, full-text search, and community submissions.',
  );

  return (
    <div className="max-w-5xl mx-auto space-y-10 py-8 px-4">
      {/* Hero section */}
      <div className="text-center space-y-4">
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-slate-900 dark:text-slate-50 leading-tight">
          Boeing-Stearman<br />
          <span className="text-amber-700 dark:text-amber-400">Information Hub</span>
        </h1>
        <p className="text-base sm:text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          The complete digital archive of Boeing-Stearman biplane engineering drawings,
          technical manuals, and service documents for the Boeing-Stearman Kaydet.
        </p>
      </div>

      {/* Search */}
      <div className="flex justify-center">
        <SearchBar />
      </div>

      {/* Quick-access cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <QuickCard
          icon={ImageIcon}
          title="Browse Drawings"
          stat={stats?.total_images?.toLocaleString() ?? '7,673'}
          description="Engineering drawings & frame diagrams"
          color="bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400"
          hoverBorder="hover:border-amber-300 dark:hover:border-amber-600"
          onClick={() => navigate('/folders/400006')}
        />
        <QuickCard
          icon={BookOpen}
          title="Manuals Library"
          stat="36+"
          description="Maintenance, parts & pilot handbooks"
          color="bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400"
          hoverBorder="hover:border-amber-300 dark:hover:border-amber-600"
          onClick={() => navigate('/manuals')}
        />
        <QuickCard
          icon={Search}
          title="Search Archive"
          stat={stats?.total_indexes?.toLocaleString() ?? '19,828'}
          description="Drawing numbers, keywords & OCR text"
          color="bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400"
          hoverBorder="hover:border-emerald-300 dark:hover:border-emerald-600"
          onClick={() => navigate('/search?q=')}
        />
        <QuickCard
          icon={Upload}
          title="Submit a Resource"
          stat="Contribute"
          description="Share drawings, manuals & photos"
          color="bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400"
          hoverBorder="hover:border-purple-300 dark:hover:border-purple-600"
          onClick={() => navigate('/submit')}
        />
      </div>

      {/* Upcoming Events Preview */}
      <UpcomingEvents />

      {/* Stearman Resources / Partners */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-4 text-center">
          Stearman Resources
        </h2>
        <a
          href="https://yesteryearaviation.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col sm:flex-row items-center gap-4 p-4 rounded-lg
            hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors duration-200 no-underline"
        >
          <img
            src="/yesteryear-logo.jpg"
            alt="Yesteryear Aviation"
            className="h-16 sm:h-12 w-auto object-contain"
          />
          <div className="text-center sm:text-left">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Yesteryear Aviation
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
              Check Yesteryear Aviation for FAA-PMA, New Surplus and As Removed Stearman Parts.
            </p>
          </div>
        </a>
      </div>

      {/* Footer note */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 pb-4">
        <p>
          A community resource for Boeing-Stearman Kaydet owners, restorers, and enthusiasts.
        </p>
      </div>
    </div>
  );
}
