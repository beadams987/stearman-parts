/**
 * PDF Viewer using PDF.js built-in viewer via iframe.
 * 
 * Uses the pre-built PDF.js viewer hosted on cdnjs which includes:
 * - Scroll, zoom, fit width, fit page (all working out of the box)
 * - Page navigation, thumbnails sidebar
 * - Text selection and search (Ctrl+F)
 * - Print support
 * - Mobile responsive
 *
 * data-testid attributes preserved for testing.
 */

interface PdfViewerProps {
  url: string;
  title?: string;
  page?: number;
}

export default function PdfViewer({ url, title, page }: PdfViewerProps) {
  // Use Mozilla's hosted PDF.js viewer with the document URL
  const encodedUrl = encodeURIComponent(url);
  const pageParam = page ? `#page=${page}` : '';
  const viewerUrl = `https://mozilla.github.io/pdf.js/web/viewer.html?file=${encodedUrl}${pageParam}`;

  return (
    <div className="w-full h-full" data-testid="pdf-viewer">
      <iframe
        src={viewerUrl}
        className="w-full h-full border-0"
        title={title || 'PDF Viewer'}
        allow="fullscreen"
      />
    </div>
  );
}
