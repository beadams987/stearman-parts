import { useParams, Link } from 'react-router-dom';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import { ChevronRight, Home, ArrowLeft } from 'lucide-react';
import { useImage } from '../api/hooks.ts';
import ImageViewer from '../components/ImageViewer.tsx';
import ImageGrid from '../components/ImageGrid.tsx';

export default function ImagePage() {
  const { id } = useParams<{ id: string }>();
  const imageId = id ? Number(id) : undefined;

  const { data: image, isLoading, error } = useImage(imageId);

  const drawingNums = image?.drawing_numbers?.join(', ') ?? '';
  const kws = image?.keywords?.join(', ') ?? '';
  const pageTitle = drawingNums || image?.file_name || 'Image';
  usePageMeta(
    pageTitle,
    `${pageTitle}${kws ? ` — ${kws}` : ''} — Stearman engineering drawing`,
  );

  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <div className="skeleton h-6 w-64 rounded" />
        <div className="skeleton h-[500px] rounded-lg" />
      </div>
    );
  }

  if (error || !image) {
    return (
      <div className="text-center py-16">
        <p className="text-lg text-slate-500 dark:text-slate-400 mb-4">
          Image not found.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400 flex-wrap">
        <Link
          to="/"
          className="flex items-center gap-1 hover:text-amber-700 dark:hover:text-amber-400"
        >
          <Home className="w-3.5 h-3.5" />
          <span>Home</span>
        </Link>
        {image.folder_path.map((f) => (
          <span key={f.id} className="flex items-center gap-1.5">
            <ChevronRight className="w-3.5 h-3.5" />
            <Link
              to={`/folders/${f.id}`}
              className="hover:text-amber-700 dark:hover:text-amber-400"
            >
              {f.folder_name}
            </Link>
          </span>
        ))}
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="text-slate-800 dark:text-slate-200 font-medium truncate max-w-[200px]">
          {image.file_name}
        </span>
      </nav>

      {/* Image viewer with metadata */}
      <ImageViewer
        imageUrl={image.render_url || image.image_url}
        downloadUrl={image.image_url}
        fileName={image.file_name}
        metadata={{
          drawingNumbers: image.drawing_numbers,
          keywords: image.keywords,
          folderName: image.folder_name,
          notes: image.notes,
          source: 'Russ Aviation Collection',
        }}
      />

      {/* Related images */}
      {image.related_images && image.related_images.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-4">
            Related Drawings
          </h2>
          <ImageGrid images={image.related_images} />
        </div>
      )}
    </div>
  );
}
