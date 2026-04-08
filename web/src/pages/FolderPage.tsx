import { useState } from 'react';
import { usePageMeta } from '../hooks/usePageMeta.ts';
import { useParams, Link } from 'react-router-dom';
import { ChevronRight, Home, Folder as FolderIcon } from 'lucide-react';
import { useFolder, useFolders, useFolderImages } from '../api/hooks.ts';
import ImageGrid from '../components/ImageGrid.tsx';

export default function FolderPage() {
  const { id } = useParams<{ id: string }>();
  const folderId = id ? Number(id) : undefined;
  const [page, setPage] = useState(1);

  const { data: folder, isLoading: folderLoading } = useFolder(folderId);
  const { data: subfolders } = useFolders(folderId);
  const { data: imageData, isLoading: imagesLoading } = useFolderImages(folderId, page);

  usePageMeta(
    folder?.folder_name ?? 'Folder',
    folder ? `Browse ${folder.folder_name} — Stearman engineering drawings` : undefined,
  );

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
          className="flex items-center gap-1 hover:text-amber-700 dark:hover:text-amber-400"
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
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {subfolders && subfolders.length > 0 && `${subfolders.length} folders`}
            {subfolders && subfolders.length > 0 && imageData && imageData.total > 0 && ' · '}
            {imageData && imageData.total > 0 && (
              <>
                {imageData.total} images
                {imageData.total_pages > 1 && ` (page ${page} of ${imageData.total_pages})`}
              </>
            )}
          </p>
        </div>
      </div>

      {/* Subfolders */}
      {subfolders && subfolders.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {subfolders.map((sub) => (
            <Link
              key={sub.id}
              to={`/folders/${sub.id}`}
              className="flex items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-200
                dark:border-slate-700 hover:shadow-md hover:border-amber-300 dark:hover:border-amber-600
                transition-all duration-200 group"
            >
              <FolderIcon className="w-8 h-8 text-amber-500 dark:text-amber-400 flex-shrink-0
                group-hover:text-amber-600 dark:group-hover:text-amber-300 transition-colors" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                  {sub.folder_name}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {sub.image_count} images
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}

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
                        ? 'bg-amber-600 text-white'
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
