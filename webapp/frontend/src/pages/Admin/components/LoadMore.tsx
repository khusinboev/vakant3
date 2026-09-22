import { useT } from "../../../i18n/useT";
import Button from "../ui/Button";

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
    <div className={`flex items-center justify-center gap-2 py-2 ${className}`}>
      {total !== null && (
        <span className="text-[11px] tabular-nums text-muted">
          {loaded !== undefined ? `${loaded} / ${total}` : t("admin.table.total", { total })}
        </span>
      )}
      {hasMore && (
        <Button
          size="sm"
          variant="secondary"
          labelKey={loading ? "admin.table.loadingMore" : "admin.table.loadMore"}
          loading={loading}
          onClick={onLoadMore}
        />
      )}
    </div>
  );
}
