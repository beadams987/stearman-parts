import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import apiClient from './client.ts';
import type {
  Folder,
  ImageDetail,
  Bundle,
  SearchResponse,
  SearchSuggestion,
  PaginatedResponse,
  Image,
  AppStats,
} from '../types.ts';

/** Fetch the folder tree, optionally filtered to children of a parent. */
export function useFolders(parentId?: number) {
  return useQuery<Folder[]>({
    queryKey: ['folders', parentId ?? 'root'],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (parentId !== undefined) {
        params.parent_id = String(parentId);
      }
      const { data } = await apiClient.get<Folder[]>('/folders', { params });
      return data;
    },
  });
}

/** Fetch a single folder by ID, including its contents. */
export function useFolder(id: number | undefined) {
  return useQuery<Folder>({
    queryKey: ['folder', id],
    queryFn: async () => {
      const { data } = await apiClient.get<Folder>(`/folders/${id}`);
      return data;
    },
    enabled: id !== undefined,
  });
}

/** Fetch paginated images for a folder. */
export function useFolderImages(folderId: number | undefined, page = 1, pageSize = 24) {
  return useQuery<PaginatedResponse<Image>>({
    queryKey: ['folder-images', folderId, page, pageSize],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Image>>(
        `/folders/${folderId}/images`,
        { params: { page, page_size: pageSize } },
      );
      return data;
    },
    enabled: folderId !== undefined,
    placeholderData: keepPreviousData,
  });
}

/** Fetch a single image with full detail. */
export function useImage(id: number | undefined) {
  return useQuery<ImageDetail>({
    queryKey: ['image', id],
    queryFn: async () => {
      const { data } = await apiClient.get<ImageDetail>(`/images/${id}`);
      return data;
    },
    enabled: id !== undefined,
  });
}

/** Fetch a bundle with all its pages. */
export function useBundle(id: number | undefined) {
  return useQuery<Bundle>({
    queryKey: ['bundle', id],
    queryFn: async () => {
      const { data } = await apiClient.get<Bundle>(`/bundles/${id}`);
      return data;
    },
    enabled: id !== undefined,
  });
}

/** Full-text search with filters and pagination. */
export function useSearch(
  query: string,
  type?: 'drawing_number' | 'keyword',
  folderId?: number,
  page = 1,
) {
  return useQuery<SearchResponse>({
    queryKey: ['search', query, type, folderId, page],
    queryFn: async () => {
      const params: Record<string, string | number> = { q: query, page };
      if (type) params.type = type;
      if (folderId) params.folder_id = folderId;
      const { data } = await apiClient.get<SearchResponse>('/search', { params });
      return data;
    },
    enabled: query.length >= 2,
    placeholderData: keepPreviousData,
  });
}

/** Debounced type-ahead search suggestions. */
export function useSearchSuggest(query: string, debounceMs = 300) {
  const [debouncedQuery, setDebouncedQuery] = useState(query);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), debounceMs);
    return () => clearTimeout(timer);
  }, [query, debounceMs]);

  return useQuery<SearchSuggestion[]>({
    queryKey: ['search-suggest', debouncedQuery],
    queryFn: async () => {
      const { data } = await apiClient.get<SearchSuggestion[]>('/search/suggest', {
        params: { q: debouncedQuery },
      });
      return data;
    },
    enabled: debouncedQuery.length >= 2,
  });
}

/** Fetch application stats for the home page. */
export function useStats() {
  return useQuery<AppStats>({
    queryKey: ['stats'],
    queryFn: async () => {
      const { data } = await apiClient.get<AppStats>('/stats');
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
