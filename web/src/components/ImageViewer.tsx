import { useRef, useCallback, useState, useEffect } from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Maximize,
  Download,
  RotateCw,
} from 'lucide-react';

interface ImageViewerProps {
  imageUrl: string;
  downloadUrl?: string;

  fileName?: string;
  metadata?: {
    drawingNumbers: string[];
    keywords: string[];
    folderName: string;
    notes: string | null;
    source?: string;
  };
  showMetadata?: boolean;
}

function ToolbarButton({
  onClick,
  title,
  children,
}: {
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="p-2 rounded-md bg-slate-700/80 hover:bg-slate-600 text-white
        transition-colors duration-150 backdrop-blur-sm cursor-pointer"
    >
      {children}
    </button>
  );
}

export default function ImageViewer({
  imageUrl,
  downloadUrl,
  fileName,
  metadata,
  showMetadata = true,
}: ImageViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const handleZoomIn = useCallback(() => {
    setScale((s) => Math.min(s * 1.5, 20));
  }, []);

  const handleZoomOut = useCallback(() => {
    setScale((s) => Math.max(s / 1.5, 0.1));
  }, []);

  const handleFitToScreen = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  const handleRotate = useCallback(() => {
    setRotation((r) => (r + 90) % 360);
  }, []);

  const handleFullScreen = useCallback(() => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setIsFullScreen(true);
    } else {
      document.exitFullscreen();
      setIsFullScreen(false);
    }
  }, []);

  const handleDownload = useCallback(() => {
    const link = document.createElement('a');
    link.href = downloadUrl || imageUrl;
    link.download = fileName ?? 'image.tif';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [imageUrl, downloadUrl, fileName]);

  // Mouse wheel zoom
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.85 : 1.18;
      setScale((s) => Math.min(Math.max(s * delta, 0.1), 20));
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, []);

  // Mouse drag to pan
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (scale <= 1) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  }, [scale, position]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Fullscreen change listener
  useEffect(() => {
    const handler = () => setIsFullScreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, []);

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full">
      {/* Viewer area */}
      <div
        ref={containerRef}
        className={`flex-1 relative ${isFullScreen ? 'bg-black' : ''}`}
        style={{ minHeight: '400px' }}
      >
        {/* Toolbar overlay */}
        <div className="absolute top-3 left-3 z-10 flex gap-1.5">
          <ToolbarButton onClick={handleZoomIn} title="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </ToolbarButton>
          <ToolbarButton onClick={handleZoomOut} title="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </ToolbarButton>
          <ToolbarButton onClick={handleFitToScreen} title="Fit to screen">
            <Maximize2 className="w-4 h-4" />
          </ToolbarButton>
          <ToolbarButton onClick={handleRotate} title="Rotate 90 degrees">
            <RotateCw className="w-4 h-4" />
          </ToolbarButton>
          <ToolbarButton onClick={handleFullScreen} title="Full screen">
            <Maximize className="w-4 h-4" />
          </ToolbarButton>
          <ToolbarButton onClick={handleDownload} title="Download original">
            <Download className="w-4 h-4" />
          </ToolbarButton>
        </div>

        {/* Zoom level indicator */}
        <div className="absolute top-3 right-3 z-10 px-2 py-1 rounded-md bg-slate-700/80 text-white text-xs backdrop-blur-sm">
          {Math.round(scale * 100)}%
        </div>

        {/* Image container */}
        <div
          className="w-full h-full rounded-lg bg-slate-800 dark:bg-slate-950 overflow-hidden flex items-center justify-center"
          style={{ minHeight: isFullScreen ? '100vh' : '500px', cursor: scale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {loading && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-white" />
            </div>
          )}
          {error ? (
            <div className="text-center text-slate-400 p-8">
              <p className="text-lg mb-2">Failed to load image</p>
              <button
                onClick={handleDownload}
                className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm"
              >
                Download Original
              </button>
            </div>
          ) : (
            <img
              ref={imgRef}
              src={imageUrl}
              alt={fileName ?? 'Engineering drawing'}
              // crossOrigin removed — Azure Blob SAS URLs don't send CORS headers
              onLoad={() => setLoading(false)}
              onError={() => { setLoading(false); setError(true); }}
              className="select-none"
              draggable={false}
              style={{
                transform: `translate(${position.x}px, ${position.y}px) scale(${scale}) rotate(${rotation}deg)`,
                transformOrigin: 'center center',
                transition: isDragging ? 'none' : 'transform 0.2s ease-out',
                maxWidth: scale <= 1 ? '100%' : 'none',
                maxHeight: scale <= 1 ? '100%' : 'none',
                objectFit: 'contain',
              }}
            />
          )}
        </div>
      </div>

      {/* Metadata panel */}
      {showMetadata && metadata && (
        <div className="lg:w-72 xl:w-80 flex-shrink-0 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4 space-y-4 overflow-y-auto max-h-[600px]">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
            Image Details
          </h3>

          {fileName && (
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                Filename
              </dt>
              <dd className="text-sm text-slate-800 dark:text-slate-200 mt-0.5 font-mono break-all">
                {fileName}
              </dd>
            </div>
          )}

          {metadata.folderName && (
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                Folder
              </dt>
              <dd className="text-sm text-slate-800 dark:text-slate-200 mt-0.5">
                {metadata.folderName}
              </dd>
            </div>
          )}

          {metadata.drawingNumbers.length > 0 && (
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                Drawing Numbers
              </dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {metadata.drawingNumbers.map((dn) => (
                  <span
                    key={dn}
                    className="inline-block px-2 py-0.5 text-xs font-mono bg-amber-50 dark:bg-amber-900/30
                      text-amber-800 dark:text-amber-300 rounded-md border border-amber-200 dark:border-amber-800"
                  >
                    {dn}
                  </span>
                ))}
              </dd>
            </div>
          )}

          {metadata.keywords.length > 0 && (
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                Keywords
              </dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {metadata.keywords.map((kw) => (
                  <span
                    key={kw}
                    className="inline-block px-2 py-0.5 text-xs bg-slate-100 dark:bg-slate-700
                      text-slate-700 dark:text-slate-300 rounded-md"
                  >
                    {kw}
                  </span>
                ))}
              </dd>
            </div>
          )}

          {metadata.notes && (
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                Notes
              </dt>
              <dd className="text-sm text-slate-800 dark:text-slate-200 mt-0.5">
                {metadata.notes}
              </dd>
            </div>
          )}

          {metadata.source && (
            <div className="pt-2 border-t border-slate-200 dark:border-slate-700">
              <dt className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                Source
              </dt>
              <dd className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 italic">
                {metadata.source}
              </dd>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
