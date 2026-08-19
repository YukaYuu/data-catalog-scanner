import Link from "next/link";
import { notFound } from "next/navigation";
import { getTable, type Column } from "@/lib/api";

export default async function TableDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const table = await getTable(Number(id));
  // getTable returns null specifically on a 404 from the API (see
  // lib/api.ts), which maps directly to Next's not-found page instead of
  // a generic error boundary.
  if (!table) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-slate-500 hover:underline">
          ← All tables
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">
          {table.schema_name ? `${table.schema_name}.${table.table_name}` : table.table_name}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          {table.source_name} &middot; {table.source_type} &middot;{" "}
          {table.row_count?.toLocaleString() ?? "unknown"} rows
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Column</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Nullable</th>
              <th className="px-4 py-3 font-medium">Key</th>
              <th className="px-4 py-3 font-medium">Nulls</th>
              <th className="px-4 py-3 font-medium">Distinct</th>
              <th className="px-4 py-3 font-medium">Min</th>
              <th className="px-4 py-3 font-medium">Max</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {table.columns.map((c) => (
              <ColumnRow key={c.ordinal_position} column={c} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ColumnRow({ column }: { column: Column }) {
  return (
    <tr className="hover:bg-slate-50">
      <td className="px-4 py-3 font-medium text-slate-900">{column.name}</td>
      <td className="px-4 py-3 text-slate-600">{column.data_type}</td>
      <td className="px-4 py-3 text-slate-600">{column.is_nullable ? "yes" : "no"}</td>
      <td className="px-4 py-3">
        {column.is_primary_key && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            PK
          </span>
        )}
      </td>
      {/* null_count/distinct_count/min/max are all nullable: a future
          connector that doesn't support profiling reports them as null
          (see ColumnProfile in the scanner), rendered as "—" here rather
          than "0" or blank, so an un-profiled column reads differently
          from a profiled column whose stats happen to be zero. */}
      <td className="px-4 py-3 text-slate-600">{column.null_count?.toLocaleString() ?? "—"}</td>
      <td className="px-4 py-3 text-slate-600">{column.distinct_count?.toLocaleString() ?? "—"}</td>
      <td className="max-w-[12rem] truncate px-4 py-3 text-slate-600" title={column.min_value ?? undefined}>
        {column.min_value ?? "—"}
      </td>
      <td className="max-w-[12rem] truncate px-4 py-3 text-slate-600" title={column.max_value ?? undefined}>
        {column.max_value ?? "—"}
      </td>
    </tr>
  );
}
