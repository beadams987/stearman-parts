import { useState, useEffect, useRef, useCallback } from 'react';
import { getDocument, GlobalWorkerOptions, version } from 'pdfjs-dist';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import {
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut,
  Maximize, Columns,
} from 'lucide-react';

GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${version}/pdf.worker.min.mjs`;

type ZoomMode = 'fit-width' | 'fit-page' | 'custom';

interface PdfViewerProps {
  url: string;
}

export default function PdfViewer({ url }: PdfViewerProps) {
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [scale, setScale] = useState(1);
  const [zoomMode, setZoomMode] = useState<ZoomMode>('fit-width');
  const [loading, setLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [pageInput, setPageInput] = useState('1');
  const [resizeKey, setResizeKey] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const renderTaskRef = useRef<{ cancel(): void } | null>(null);

  // Load PDF document
  useEffect(() => {
    setLoading(true);
    setLoadProgress(0);
    setPdfDoc(null);
    setCurrentPage(1);
    setPageInput('1');

    const loadingTask = getDocument({ url });

    loadingTask.onProgress = ({ loaded, total }: { loaded: number; total: number }) => {
      if (total > 0) {
        setLoadProgress(Math.round((loaded / total) * 100));
      }
    };

    loadingTask.promise
      .then((pdf: PDFDocumentProxy) => {
        setPdfDoc(pdf);
        setTotalPages(pdf.numPages);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });

    return () => {
      loadingTask.destroy();
    };
  }, [url]);

  // ResizeObserver to re-render on container resize (for fit modes)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver(() => {
      setResizeKey((k) => k + 1);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Render current page
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current || !containerRef.current) return;

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    setRendering(true);

    pdfDoc.getPage(currentPage).then((page) => {
      const container = containerRef.current;
      const canvas = canvasRef.current;
      if (!container || !canvas) return;

      let effectiveScale = scale;
      if (zoomMode !== 'custom') {
        const baseViewport = page.getViewport({ scale: 1 });
        const containerWidth = container.clientWidth - 32;
        const containerHeight = container.clientHeight - 32;

        if (zoomMode === 'fit-width') {
          effectiveScale = containerWidth / baseViewport.width;
        } else {
          effectiveScale = Math.min(
            containerWidth / baseViewport.width,
            containerHeight / baseViewport.height,
          );
        }
      }

      const viewport = page.getViewport({ scale: effectiveScale });
      const context = canvas.getContext('2d');
      if (!context) return;

      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
      context.scale(dpr, dpr);

      const renderTask = page.render({ canvasContext: context, viewport });
      renderTaskRef.current = renderTask;

      renderTask.promise
        .then(() => {
          setRendering(false);
          renderTaskRef.current = null;
        })
        .catch((err: Error) => {
          if (err?.name !== 'RenderingCancelledException') {
            setRendering(false);
          }
        });
    });
    // resizeKey forces re-render when container resizes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdfDoc, currentPage, scale, zoomMode, resizeKey]);

  // Navigation
  const goToPage = useCallback(
    (page: number) => {
      const p = Math.max(1, Math.min(page, totalPages));
      setCurrentPage(p);
      setPageInput(String(p));
    },
    [totalPages],
  );

  const prevPage = useCallback(() => goToPage(currentPage - 1), [currentPage, goToPage]);
  const nextPage = useCallback(() => goToPage(currentPage + 1), [currentPage, goToPage]);

  // Zoom
  const zoomIn = useCallback(() => {
    setZoomMode('custom');
    setScale((s) => Math.min(s * 1.25, 5));
  }, []);

  const zoomOut = useCallback(() => {
    setZoomMode('custom');
    setScale((s) => Math.max(s / 1.25, 0.25));
  }, []);

  const fitWidth = useCallback(() => setZoomMode('fit-width'), []);
  const fitPage = useCallback(() => setZoomMode('fit-page'), []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT') return;

      switch (e.key) {
        case 'ArrowLeft':
          prevPage();
          e.preventDefault();
          break;
        case 'ArrowRight':
          nextPage();
          e.preventDefault();
          break;
        case '+':
        case '=':
          zoomIn();
          e.preventDefault();
          break;
        case '-':
          zoomOut();
          e.preventDefault();
          break;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [prevPage, nextPage, zoomIn, zoomOut]);

  // Page input form
  const handlePageSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const num = parseInt(pageInput, 10);
    if (!isNaN(num)) goToPage(num);
  };

  // Loading state with progress bar
  if (loading) {
    return (
      <div data-testid="pdf-viewer" className="flex-1 flex flex-col items-center justify-center bg-slate-800 text-white">
        <div className="w-64 space-y-4">
          <div className="text-center text-sm text-slate-300">Loading PDF…</div>
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-500 rounded-full transition-all duration-300"
              style={{ width: `${loadProgress}%` }}
            />
          </div>
          <div className="text-center text-xs text-slate-400">{loadProgress}%</div>
        </div>
      </div>
    );
  }

  if (!pdfDoc) {
    return (
      <div data-testid="pdf-viewer" className="flex-1 flex items-center justify-center bg-slate-800 text-white">
        <p className="text-slate-400">Failed to load PDF.</p>
      </div>
    );
  }

  return (
    <div data-testid="pdf-viewer" className="flex-1 flex flex-col bg-slate-800">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-700 text-white text-sm gap-2">
        {/* Page navigation */}
        <div className="flex items-center gap-1">
          <button
            data-testid="pdf-prev"
            onClick={prevPage}
            disabled={currentPage <= 1}
            className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30 cursor-pointer disabled:cursor-default"
            aria-label="Previous page"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <form onSubmit={handlePageSubmit} className="flex items-center gap-1">
            <input
              type="text"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              className="w-12 text-center bg-slate-800 border border-slate-600 rounded px-1 py-0.5 text-xs"
              aria-label="Page number"
            />
          </form>
          <span data-testid="pdf-page-display" className="text-xs text-slate-400">
            / {totalPages}
          </span>
          <button
            data-testid="pdf-next"
            onClick={nextPage}
            disabled={currentPage >= totalPages}
            className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30 cursor-pointer disabled:cursor-default"
            aria-label="Next page"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            data-testid="pdf-zoom-out"
            onClick={zoomOut}
            className="p-1.5 rounded hover:bg-slate-700 cursor-pointer"
            aria-label="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            data-testid="pdf-zoom-in"
            onClick={zoomIn}
            className="p-1.5 rounded hover:bg-slate-700 cursor-pointer"
            aria-label="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={fitWidth}
            title="Fit width"
            className={`p-1.5 rounded cursor-pointer ${zoomMode === 'fit-width' ? 'bg-slate-700' : 'hover:bg-slate-700'}`}
            aria-label="Fit width"
          >
            <Columns className="w-4 h-4" />
          </button>
          <button
            onClick={fitPage}
            title="Fit page"
            className={`p-1.5 rounded cursor-pointer ${zoomMode === 'fit-page' ? 'bg-slate-700' : 'hover:bg-slate-700'}`}
            aria-label="Fit page"
          >
            <Maximize className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Canvas area */}
      <div ref={containerRef} className="flex-1 overflow-auto flex justify-center p-4">
        <canvas ref={canvasRef} className={`transition-opacity ${rendering ? 'opacity-50' : ''}`} />
      </div>
    </div>
  );
}
