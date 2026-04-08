import { useState, useCallback, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import ImageViewer from './ImageViewer.tsx';
import type { Image } from '../types.ts';

interface BundleViewerProps {
  pages: Image[];
  drawingNumbers: string[];
  keywords: string[];
  folderName: string;
  notes: string | null;
}

export default function BundleViewer({
  pages,
  drawingNumbers,
  keywords,
  folderName,
  notes,
}: BundleViewerProps) {
  const [activePage, setActivePage] = useState(0);

  const goToPrev = useCallback(() => {
    setActivePage((p) => Math.max(0, p - 1));
  }, []);

  const goToNext = useCallback(() => {
    setActivePage((p) => Math.min(pages.length - 1, p + 1));
  }, [pages.length]);

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowLeft') {
        goToPrev();
      } else if (e.key === 'ArrowRight') {
        goToNext();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [goToPrev, goToNext]);

  if (pages.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500 dark:text-slate-400">
        No pages in this bundle.
      </div>
    );
  }

  const currentImage = pages[activePage];
  // Use the pre-rendered JPEG URL, falling back to thumbnail
  const imageUrl = currentImage.render_url || currentImage.thumbnail_url;

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Page navigation bar */}
      <div className="flex items-center justify-between bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-2">
        <button
          onClick={goToPrev}
          disabled={activePage === 0}
          className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-md
            bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600
            disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer
            text-slate-700 dark:text-slate-300"
        >
          <ChevronLeft className="w-4 h-4" />
          Previous
        </button>

        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Page {activePage + 1} of {pages.length}
        </span>

        <button
          onClick={goToNext}
          disabled={activePage === pages.length - 1}
          className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-md
            bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600
            disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer
            text-slate-700 dark:text-slate-300"
        >
          Next
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Image viewer */}
      <div className="flex-1">
        <ImageViewer
          imageUrl={imageUrl}
          fileName={currentImage.file_name}
          metadata={{
            drawingNumbers: drawingNumbers.length > 0 ? drawingNumbers : currentImage.drawing_numbers,
            keywords: keywords.length > 0 ? keywords : currentImage.keywords,
            folderName,
            notes,
          }}
        />
      </div>

      {/* Thumbnail strip */}
      <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {pages.map((page, index) => (
            <button
              key={page.id}
              onClick={() => setActivePage(index)}
              className={`flex-shrink-0 w-20 h-20 rounded-md border-2 overflow-hidden cursor-pointer
                transition-all duration-150
                ${
                  index === activePage
                    ? 'border-amber-500 ring-2 ring-amber-500/30'
                    : 'border-slate-200 dark:border-slate-600 hover:border-amber-300 dark:hover:border-amber-500'
                }`}
            >
              <img
                src={page.thumbnail_url}
                alt={`Page ${index + 1}`}
                className="w-full h-full object-contain bg-slate-50 dark:bg-slate-900 p-0.5"
                loading="lazy"
              />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
