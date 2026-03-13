import { useEffect, useRef, useCallback } from 'react';
import OpenSeadragon from 'openseadragon';
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
  dziUrl?: string | null;
  fileName?: string;
  metadata?: {
    drawingNumbers: string[];
    keywords: string[];
    folderName: string;
    notes: string | null;
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
  dziUrl,
  fileName,
  metadata,
  showMetadata = true,
}: ImageViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null);
  const osdRef = useRef<OpenSeadragon.Viewer | null>(null);

  useEffect(() => {
    if (!viewerRef.current) return;

    const tileSource = dziUrl
      ? { type: 'image', url: dziUrl }
      : { type: 'image' as const, url: imageUrl };

    const viewer = OpenSeadragon({
      element: viewerRef.current,
      tileSources: tileSource,
      prefixUrl: '',
      showNavigationControl: false,
      showNavigator: true,
      navigatorPosition: 'BOTTOM_RIGHT',
      navigatorSizeRatio: 0.15,
      minZoomLevel: 0.1,
      maxZoomLevel: 20,
      visibilityRatio: 0.5,
      constrainDuringPan: false,
      animationTime: 0.3,
      gestureSettingsMouse: {
        scrollToZoom: true,
        clickToZoom: true,
        dblClickToZoom: true,
      },
      gestureSettingsTouch: {
        pinchToZoom: true,
        flickEnabled: true,
      },
    });

    osdRef.current = viewer;

    return () => {
      viewer.destroy();
      osdRef.current = null;
    };
  }, [imageUrl, dziUrl]);

  const handleZoomIn = useCallback(() => {
    osdRef.current?.viewport.zoomBy(1.5);
  }, []);

  const handleZoomOut = useCallback(() => {
    osdRef.current?.viewport.zoomBy(0.67);
  }, []);

  const handleFitToScreen = useCallback(() => {
    osdRef.current?.viewport.goHome();
  }, []);

  const handleFullScreen = useCallback(() => {
    osdRef.current?.setFullScreen(!osdRef.current.isFullPage());
  }, []);

  const handleRotate = useCallback(() => {
    const current = osdRef.current?.viewport.getRotation() ?? 0;
    osdRef.current?.viewport.setRotation(current + 90);
  }, []);

  const handleDownload = useCallback(() => {
    const link = document.createElement('a');
    link.href = downloadUrl || imageUrl;
    link.download = fileName ?? 'image.tif';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [imageUrl, fileName]);

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full">
      {/* Viewer area */}
      <div className="flex-1 relative min-h-[400px] lg:min-h-[600px]">
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
          <ToolbarButton onClick={handleDownload} title="Download">
            <Download className="w-4 h-4" />
          </ToolbarButton>
        </div>

        {/* OSD container */}
        <div
          ref={viewerRef}
          className="w-full h-full rounded-lg bg-slate-800 dark:bg-slate-950"
          style={{ minHeight: '400px' }}
        />
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
                    className="inline-block px-2 py-0.5 text-xs font-mono bg-blue-50 dark:bg-blue-900/30
                      text-blue-700 dark:text-blue-300 rounded-md border border-blue-200 dark:border-blue-800"
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
        </div>
      )}
    </div>
  );
}
