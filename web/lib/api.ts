// Thin, typed wrapper around the Go API (api/catalog). Field names are
// snake_case to match the JSON the API actually emits (its Go structs use
// snake_case json tags), rather than translating to camelCase -- less
// mapping code, and the shape on the wire stays visible in the type.

export type TableSummary = {
  id: number;
  source_name: string;
  source_type: string;
  schema_name: string;
  table_name: string;
  row_count: number | null;
  column_count: number;
};

export type Column = {
  name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  ordinal_position: number;
  null_count: number | null;
  distinct_count: number | null;
  min_value: string | null;
  max_value: string | null;
};

export type TableDetail = TableSummary & {
  columns: Column[];
};

// CATALOG_API_URL is only ever read on the server (these functions run in
// Server Components / route handlers, never in the browser -- see the "Why
// Server Components" note in web/README.md). That also means the Go API
// never needs CORS headers: the browser only ever talks to the Next.js
// server, not directly to :8080.
const API_URL = process.env.CATALOG_API_URL ?? "http://localhost:8080";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`catalog API ${path} returned ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function listTables(): Promise<TableSummary[]> {
  return apiFetch<TableSummary[]>("/api/tables");
}

export function searchTables(query: string): Promise<TableSummary[]> {
  return apiFetch<TableSummary[]>(`/api/search?q=${encodeURIComponent(query)}`);
}

// Returns null (rather than throwing) on a 404 specifically, so the page
// component can render a proper "not found" view instead of a generic
// error boundary -- the API's ErrNotFound maps to a plain 404 here.
export async function getTable(id: number): Promise<TableDetail | null> {
  const res = await fetch(`${API_URL}/api/tables/${id}`, { cache: "no-store" });
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`catalog API /api/tables/${id} returned ${res.status}`);
  }
  return res.json() as Promise<TableDetail>;
}
