import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { useFolder, useFolderImages } from '../api/hooks.ts';
import ImageGrid from '../components/ImageGrid.tsx';

export default function FolderPage() {
  const { id } = useParams<{ id: string }>();
  const folderId = id ? Number(id) : undefined;
  const [page, setPage] = useState(1);

  const { data: folder, isLoading: folderLoading } = useFolder(folderId);
  const { data: imageData, isLoading: imagesLoading } = useFolderImages(folderId, page);

  if (folderLoading) {
    return (
      <div className="space-y-4 p-4">
        <div className="skeleton h-6 w-48 rounded" />
        <div className="skeleton h-8 w-64 rounded" />
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="skeleton aspect-square rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
        <Link
          to="/"
          className="flex items-center gap-1 hover:text-blue-600 dark:hover:text-blue-400"
        >
          <Home className="w-3.5 h-3.5" />
          <span>Home</span>
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        {folder && (
          <span className="text-slate-800 dark:text-slate-200 font-medium">
            {folder.folder_name}
          </span>
        )}
      </nav>

      {/* Folder header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {folder?.folder_name ?? 'Loading...'}
          </h1>
          {imageData && (
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {imageData.total} images
              {imageData.total_pages > 1 && ` (page ${page} of ${imageData.total_pages})`}
            </p>
          )}
        </div>
      </div>

      {/* Image grid */}
      {imagesLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="skeleton aspect-square rounded-lg" />
          ))}
        </div>
      ) : imageData ? (
        <ImageGrid images={imageData.items} />
      ) : null}

      {/* Pagination */}
      {imageData && imageData.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 text-sm rounded-md bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600
              text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700
              disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            Previous
          </button>

          <div className="flex gap-1">
            {Array.from({ length: Math.min(imageData.total_pages, 7) }, (_, i) => {
              let pageNum: number;
              if (imageData.total_pages <= 7) {
                pageNum = i + 1;
              } else if (page <= 4) {
                pageNum = i + 1;
              } else if (page >= imageData.total_pages - 3) {
                pageNum = imageData.total_pages - 6 + i;
              } else {
                pageNum = page - 3 + i;
              }

              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`w-9 h-9 text-sm rounded-md cursor-pointer
                    ${
                      page === pageNum
                        ? 'bg-blue-600 text-white'
                        : 'bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                    }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setPage((p) => Math.min(imageData.total_pages, p + 1))}
            disabled={page === imageData.total_pages}
            className="px-4 py-2 text-sm rounded-md bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600
              text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700
              disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
