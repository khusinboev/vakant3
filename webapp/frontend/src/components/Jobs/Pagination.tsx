type Props = {
  page: number;
  lastPage: number;
  onChange: (next: number) => void;
};

export default function Pagination({ page, lastPage, onChange }: Props) {
  if (lastPage <= 1) return null;

  // Build a window of visible page numbers: always show 1, lastPage, and ±2 around current page
  const pages: (number | "ellipsis-left" | "ellipsis-right")[] = [];
  const start = Math.max(2, page - 2);
  const end = Math.min(lastPage - 1, page + 2);

  pages.push(1);
  if (start > 2) pages.push("ellipsis-left");
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < lastPage - 1) pages.push("ellipsis-right");
  if (lastPage > 1) pages.push(lastPage);

  return (
    <div className="card flex items-center justify-center gap-1 px-3 py-2 flex-wrap">
      <button
        className="tap-target rounded-full border border-slate-300 px-3 text-sm disabled:opacity-40"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        aria-label="Oldingi sahifa"
      >
        ←
      </button>

      {pages.map((p, i) =>
        p === "ellipsis-left" || p === "ellipsis-right" ? (
          <span key={p + String(i)} className="px-1 text-slate-400 text-sm select-none">
            …
          </span>
        ) : (
          <button
            key={p}
            className={`tap-target min-w-[2.25rem] rounded-full border text-sm transition ${
              p === page
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 text-slate-600 hover:border-slate-500 hover:bg-slate-50"
            }`}
            onClick={() => onChange(p as number)}
            aria-current={p === page ? "page" : undefined}
          >
            {p}
          </button>
        )
      )}

      <button
        className="tap-target rounded-full border border-slate-300 px-3 text-sm disabled:opacity-40"
        disabled={page >= lastPage}
        onClick={() => onChange(page + 1)}
        aria-label="Keyingi sahifa"
      >
        →
      </button>
    </div>
  );
}
