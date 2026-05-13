type Props = {
  page: number;
  lastPage: number;
  onChange: (next: number) => void;
};

export default function Pagination({ page, lastPage, onChange }: Props) {
  return (
    <div className="card flex items-center justify-between gap-3 px-3 py-2">
      <button className="tap-target rounded-full border border-slate-300 px-4 text-sm disabled:opacity-40" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        ←
      </button>
      <span className="text-sm font-medium text-slate-600">
        {page} / {lastPage}
      </span>
      <button className="tap-target rounded-full border border-slate-300 px-4 text-sm disabled:opacity-40" disabled={page >= lastPage} onClick={() => onChange(page + 1)}>
        →
      </button>
    </div>
  );
}
