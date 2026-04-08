import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layers } from 'lucide-react';
import type { Image } from '../types.ts';

interface ImageGridProps {
  images: Image[];
}

function ImageCard({ image }: { image: Image }) {
  const navigate = useNavigate();
  const [loaded, setLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);

  const handleClick = useCallback(() => {
    if (image.bundle_id) {
      navigate(`/bundles/${image.bundle_id}`);
    } else {
      navigate(`/images/${image.id}`);
    }
  }, [image.id, image.bundle_id, navigate]);

  const drawingNum = image.drawing_numbers.length > 0 ? image.drawing_numbers[0] : null;

  return (
    <button
      onClick={handleClick}
      className="group bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700
        overflow-hidden hover:shadow-lg hover:border-amber-300 dark:hover:border-amber-600
        transition-shadow duration-200 text-left w-full cursor-pointer"
    >
      {/* Thumbnail */}
      <div className="relative aspect-square bg-slate-100 dark:bg-slate-900 overflow-hidden">
        {!loaded && !imgError && (
          <div className="absolute inset-0 skeleton" />
        )}
        {!imgError ? (
          <img
            src={image.thumbnail_url}
            alt={image.file_name}
            loading="lazy"
            onLoad={() => setLoaded(true)}
            onError={() => setImgError(true)}
            className={`w-full h-full object-contain p-1 transition-opacity duration-200
              ${loaded ? 'opacity-100' : 'opacity-0'}
              group-hover:scale-105 transition-transform duration-200`}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-slate-400 dark:text-slate-600">
            <span className="text-xs">No preview</span>
          </div>
        )}

        {/* Bundle badge */}
        {image.bundle_id && (
          <div className="absolute top-2 right-2 bg-amber-600 text-white rounded-full p-1.5 shadow-md">
            <Layers className="w-3.5 h-3.5" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-2.5">
        <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
          {image.file_name}
        </p>
        {drawingNum && (
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5 truncate font-mono">
            {drawingNum}
          </p>
        )}
        {image.keywords.length > 0 && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">
            {image.keywords.join(', ')}
          </p>
        )}
      </div>
    </button>
  );
}

export default function ImageGrid({ images }: ImageGridProps) {
  if (images.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500 dark:text-slate-400">
        <p className="text-lg">No images in this folder.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
      {images.map((image) => (
        <ImageCard key={image.id} image={image} />
      ))}
    </div>
  );
}
