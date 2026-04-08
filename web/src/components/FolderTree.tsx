import { useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Folder as FolderIcon,
  FolderOpen,
  ChevronRight,
  ChevronDown,
} from 'lucide-react';
import { useFolders } from '../api/hooks.ts';
import type { Folder } from '../types.ts';

interface FolderNodeProps {
  folder: Folder;
  level: number;
  currentFolderId: number | undefined;
  onNavigate: (id: number) => void;
}

function FolderNode({ folder, level, currentFolderId, onNavigate }: FolderNodeProps) {
  const [expanded, setExpanded] = useState(false);
  const isActive = folder.id === currentFolderId;
  const hasChildren = folder.children && folder.children.length > 0;

  const handleToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (hasChildren) {
        setExpanded((prev) => !prev);
      }
    },
    [hasChildren],
  );

  const handleClick = useCallback(() => {
    onNavigate(folder.id);
    if (hasChildren && !expanded) {
      setExpanded(true);
    }
  }, [folder.id, hasChildren, expanded, onNavigate]);

  return (
    <div>
      <button
        onClick={handleClick}
        className={`
          w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-left
          hover:bg-slate-100 dark:hover:bg-slate-700
          ${isActive ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 font-medium' : 'text-slate-700 dark:text-slate-300'}
        `}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
      >
        <span
          onClick={handleToggle}
          className="flex-shrink-0 w-4 h-4 flex items-center justify-center cursor-pointer"
        >
          {hasChildren ? (
            expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            )
          ) : (
            <span className="w-3.5" />
          )}
        </span>
        {expanded || isActive ? (
          <FolderOpen className="w-4 h-4 flex-shrink-0 text-amber-600 dark:text-amber-400" />
        ) : (
          <FolderIcon className="w-4 h-4 flex-shrink-0 text-slate-400 dark:text-slate-500" />
        )}
        <span className="truncate">{folder.folder_name}</span>
        {folder.image_count > 0 && (
          <span className="ml-auto text-xs text-slate-400 dark:text-slate-500 flex-shrink-0">
            {folder.image_count}
          </span>
        )}
      </button>

      {expanded && hasChildren && (
        <div>
          {folder.children!.map((child) => (
            <FolderNode
              key={child.id}
              folder={child}
              level={level + 1}
              currentFolderId={currentFolderId}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FolderTree() {
  const { id } = useParams<{ id: string }>();
  const currentFolderId = id ? Number(id) : undefined;
  const navigate = useNavigate();
  const { data: folders, isLoading, error } = useFolders();

  const handleNavigate = useCallback(
    (folderId: number) => {
      navigate(`/folders/${folderId}`);
    },
    [navigate],
  );

  if (isLoading) {
    return (
      <div className="p-4 space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="skeleton h-7 rounded-md" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-red-500 dark:text-red-400">
        Failed to load folders. Please try again.
      </div>
    );
  }

  if (!folders || folders.length === 0) {
    return (
      <div className="p-4 text-sm text-slate-500 dark:text-slate-400">
        No folders found.
      </div>
    );
  }

  return (
    <nav className="p-2 space-y-0.5">
      {folders.map((folder) => (
        <FolderNode
          key={folder.id}
          folder={folder}
          level={0}
          currentFolderId={currentFolderId}
          onNavigate={handleNavigate}
        />
      ))}
    </nav>
  );
}
