/** Folder in the hierarchical navigation tree. */
export interface Folder {
  id: number;
  parent_id: number | null;
  folder_name: string;
  notes: string | null;
  image_count: number;
  children_count: number;
  children?: Folder[];
}

/** Lightweight image record returned in lists and grids. */
export interface Image {
  id: number;
  folder_id: number;
  file_name: string;
  image_position: number;
  bundle_id: number | null;
  bundle_offset: number | null;
  thumbnail_url: string;
  render_url: string | null;
  drawing_numbers: string[];
  keywords: string[];
}

/** Full image detail including the full-resolution URL and metadata. */
export interface ImageDetail extends Image {
  image_url: string;
  render_url: string | null;

  notes: string | null;
  folder_name: string;
  folder_path: Folder[];
  related_images: Image[];
}

/** A multi-page bundle grouping related images. */
export interface Bundle {
  id: number;
  folder_id: number;
  folder_name: string;
  image_position: number;
  notes: string | null;
  drawing_numbers: string[];
  keywords: string[];
  pages: Image[];
}

/** A single search result item. */
export interface SearchResult {
  id: number;
  type: 'image' | 'bundle';
  file_name: string;
  thumbnail_url: string;
  folder_name: string;
  folder_id: number;
  matched_field: 'drawing_number' | 'keyword';
  matched_value: string;
  drawing_numbers: string[];
  keywords: string[];
  bundle_id: number | null;
  page_count: number | null;
  ocr_snippet: string | null;
}

/** Paginated search response. */
export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query: string;
}

/** A suggestion from the type-ahead endpoint. */
export interface SearchSuggestion {
  value: string;
  type: 'drawing_number' | 'keyword';
  count: number;
}

/** Generic paginated API response wrapper. */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Stats for the home page. */
export interface AppStats {
  total_images: number;
  total_folders: number;
  total_bundles: number;
  total_indexes: number;
}
