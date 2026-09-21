import { useT } from "../../../i18n/useT";

export type LoadMoreProps = {
  onLoadMore: () => void;
  hasMore: boolean;
  loading?: boolean;
  /** Server-reported total, shown next to the button when known. */
  total?: number | null;
  /** How many rows are on screen right now. */
  loaded?: number;
  className?: string;
};

/** The cursor-pagination footer shared by every admin list. */
export default function LoadMore({
  onLoadMore,
  hasMore,
  loading = false,
  total = null,
  loaded,
  className = "",
}: LoadMoreProps) {
  const t = useT();
  if (!hasMore && total === null) return null;

  return (
    <div className={`flex items-center justify-center gap-3 py-3 ${className}`}>
      {total !== null && (
        <span className="text-xs text-muted">
          {loaded !== undefined ? `${loaded} / ${total}` : t("admin.table.total", { total })}
        </span>
      )}
      {hasMore && (
        <button
          type="button"
          onClick={onLoadMore}
          disabled={loading}
          className="tap-target rounded-xl border border-border bg-surface px-4 py-2 text-xs font-semibold text-text disabled:opacity-60"
        >
          {loading ? t("admin.table.loadingMore") : t("admin.table.loadMore")}
        </button>
      )}
    </div>
  );
}
