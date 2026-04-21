import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { trackEvent } from '../lib/appInsights.ts';

export function useDwellTime(): void {
  const location = useLocation();
  const startRef = useRef<number>(0);

  useEffect(() => {
    startRef.current = Date.now();
    const page = location.pathname + location.search;

    return () => {
      const seconds = Math.round((Date.now() - startRef.current) / 1000);
      if (seconds <= 0) return;
      trackEvent('DwellTime', { page, seconds });
    };
  }, [location.pathname, location.search]);
}

export function trackSearch(query: string, type: string = 'all'): void {
  const trimmed = query.trim();
  if (trimmed.length === 0) return;
  trackEvent('Search', { query: trimmed, type });
}

export function trackDownload(filename: string, type: string): void {
  if (!filename) return;
  trackEvent('Download', { filename, type });
}
