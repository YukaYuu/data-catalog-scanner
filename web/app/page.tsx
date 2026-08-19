import Link from "next/link";
import { listTables, searchTables, type TableSummary } from "@/lib/api";

// A plain GET <form> (no client JS) so search works as a normal navigation
// to /?q=... -- this is a read-only catalog browser, not an app that needs
// client-side state, so there's no reason to reach for "use client" here.
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const tables = q ? await searchTables(q) : await listTables();

  return (
    <div className="space-y-6">
      <form action="/" method="GET" className="flex gap-2">
        <input
          type="text"
          name="q"
          defaultValue={q ?? ""}
          placeholder="Search table or column names..."
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Search
        </button>
        {q && (
          <Link
            href="/"
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Clear
          </Link>
        )}
      </form>

      {q && (
        <p className="text-sm text-slate-500">
          {tables.length} result{tables.length === 1 ? "" : "s"} for &ldquo;{q}&rdquo;
        </p>
      )}

      {tables.length === 0 ? (
        <p className="text-sm text-slate-500">No tables found.</p>
      ) : (
        <TableList tables={tables} />
      )}
    </div>
  );
}

function TableList({ tables }: { tables: TableSummary[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">Table</th>
            <th className="px-4 py-3 font-medium">Source</th>
            <th className="px-4 py-3 font-medium">Engine</th>
            <th className="px-4 py-3 font-medium text-right">Rows</th>
            <th className="px-4 py-3 font-medium text-right">Columns</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tables.map((t) => (
            <tr key={t.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link href={`/tables/${t.id}`} className="font-medium text-slate-900 hover:underline">
                  {t.schema_name ? `${t.schema_name}.${t.table_name}` : t.table_name}
                </Link>
              </td>
              <td className="px-4 py-3 text-slate-600">{t.source_name}</td>
              <td className="px-4 py-3">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {t.source_type}
                </span>
              </td>
              <td className="px-4 py-3 text-right text-slate-600">
                {t.row_count?.toLocaleString() ?? "—"}
              </td>
              <td className="px-4 py-3 text-right text-slate-600">{t.column_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
