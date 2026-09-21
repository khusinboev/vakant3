import type { ElementType, ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useIsDesktopSm } from "../hooks/useMediaQuery";
import EmptyState from "./EmptyState";
import ErrorCard from "./ErrorCard";
import LoadMore from "./LoadMore";

export type SortDirection = "asc" | "desc";
export type SortState = { key: string; direction: SortDirection } | null;

export type Column<T> = {
  /** Unique per table; also the React key of the cell. */
  key: string;
  labelKey: TranslationKey;
  /** Extra classes on both the `<th>` and the `<td>`. */
  className?: string;
  /** Cell content. Defaults to `String(row[key])`. */
  render?: (row: T) => ReactNode;
  /** Present => the header is a sort button and reports this key upwards. */
  sortKey?: string;
  align?: "left" | "center" | "right";
  /** Hide this column in the mobile card fallback. */
  hideOnCard?: boolean;
};

export type DataTableProps<T> = {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string | number;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyKey?: TranslationKey;
  emptyIcon?: ElementType;
  onLoadMore?: () => void;
  hasMore?: boolean;
  loadingMore?: boolean;
  total?: number | null;
  /** Replaces the generated `<td>` cells; must return `<td>` elements. */
  renderRow?: (row: T) => ReactNode;
  /** Mobile (<768px) card body. Falls back to the first three columns. */
  renderCard?: (row: T) => ReactNode;
  onRowClick?: (row: T) => void;
  stickyHeader?: boolean;
  dense?: boolean;
  /** Sort state is lifted: the table only reports intent. */
  sort?: SortState;
  onSortChange?: (sort: SortState) => void;
  /** Accessible name of the table. */
  captionKey?: TranslationKey;
  className?: string;
};

const ALIGN: Record<NonNullable<Column<unknown>["align"]>, string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

function cellValue<T>(row: T, column: Column<T>): ReactNode {
  if (column.render) return column.render(row);
  const raw = (row as Record<string, unknown>)[column.key];
  return raw === null || raw === undefined ? "—" : String(raw);
}

/**
 * The one admin list primitive: a real `<table>` on tablet/desktop and a stack
 * of cards on phones, with loading / error / empty / load-more all handled.
 *
 *   <DataTable
 *     columns={columns} rows={users.items} getRowId={(u) => u.user_id}
 *     loading={users.isLoading} error={users.error} onRetry={users.refetch}
 *     hasMore={users.hasMore} onLoadMore={users.loadMore} total={users.total}
 *     sort={sort} onSortChange={setSort}
 *   />
 */
export default function DataTable<T>({
  columns,
  rows,
  getRowId,
  loading = false,
  error = null,
  onRetry,
  emptyKey = "admin.table.empty",
  emptyIcon,
  onLoadMore,
  hasMore = false,
  loadingMore = false,
  total = null,
  renderRow,
  renderCard,
  onRowClick,
  stickyHeader = false,
  dense = false,
  sort = null,
  onSortChange,
  captionKey,
  className = "",
}: DataTableProps<T>) {
  const t = useT();
  const isWide = useIsDesktopSm();

  if (error) return <ErrorCard error={error} onRetry={onRetry} />;

  if (loading && rows.length === 0) {
    return (
      <div className={`space-y-2 ${className}`} aria-busy="true" aria-live="polite">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="h-12 animate-pulse rounded-xl bg-surfaceAlt" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return <EmptyState icon={emptyIcon} labelKey={emptyKey} className={className} />;
  }

  const toggleSort = (sortKey: string) => {
    if (!onSortChange) return;
    if (sort?.key === sortKey) {
      onSortChange(sort.direction === "desc" ? { key: sortKey, direction: "asc" } : null);
    } else {
      onSortChange({ key: sortKey, direction: "desc" });
    }
  };

  const pad = dense ? "px-3 py-2" : "px-3 py-3";

  // ── Mobile: cards ────────────────────────────────────────────────────────
  if (!isWide) {
    const cardColumns = columns.filter((c) => !c.hideOnCard).slice(0, 3);
    return (
      <div className={className}>
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={getRowId(row)}>
              <div
                role={onRowClick ? "button" : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                className={`card p-3 ${onRowClick ? "tap-target cursor-pointer" : ""}`}
              >
                {renderCard ? (
                  renderCard(row)
                ) : (
                  <dl className="space-y-1">
                    {cardColumns.map((column) => (
                      <div key={column.key} className="flex items-baseline justify-between gap-3">
                        <dt className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-muted">
                          {t(column.labelKey)}
                        </dt>
                        <dd className="min-w-0 truncate text-right text-sm text-text">
                          {cellValue(row, column)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            </li>
          ))}
        </ul>
        {onLoadMore && (
          <LoadMore
            onLoadMore={onLoadMore}
            hasMore={hasMore}
            loading={loadingMore}
            total={total}
            loaded={rows.length}
          />
        )}
      </div>
    );
  }

  // ── Tablet / desktop: table ──────────────────────────────────────────────
  return (
    <div className={className}>
      <div className="card overflow-x-auto">
        <table className="w-full min-w-full border-collapse text-sm">
          {captionKey && <caption className="sr-only">{t(captionKey)}</caption>}
          <thead className={stickyHeader ? "sticky top-0 z-10 bg-surfaceAlt" : "bg-surfaceAlt"}>
            <tr>
              {columns.map((column) => {
                const active = sort?.key === column.sortKey;
                const align = ALIGN[column.align ?? "left"];
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={
                      column.sortKey
                        ? active
                          ? sort?.direction === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                        : undefined
                    }
                    className={`${pad} ${align} text-[11px] font-semibold uppercase tracking-wide text-muted ${column.className ?? ""}`}
                  >
                    {column.sortKey && onSortChange ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column.sortKey!)}
                        aria-label={t("admin.table.sort", { label: t(column.labelKey) })}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide hover:text-text"
                      >
                        {t(column.labelKey)}
                        {!active && <ChevronsUpDown size={11} aria-hidden="true" />}
                        {active && sort?.direction === "asc" && <ArrowUp size={11} aria-hidden="true" />}
                        {active && sort?.direction === "desc" && <ArrowDown size={11} aria-hidden="true" />}
                      </button>
                    ) : (
                      t(column.labelKey)
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <tr
                key={getRowId(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === "Enter") onRowClick(row);
                      }
                    : undefined
                }
                className={onRowClick ? "cursor-pointer hover:bg-surfaceAlt" : undefined}
              >
                {renderRow
                  ? renderRow(row)
                  : columns.map((column) => (
                      <td
                        key={column.key}
                        className={`${pad} ${ALIGN[column.align ?? "left"]} align-middle text-text ${column.className ?? ""}`}
                      >
                        {cellValue(row, column)}
                      </td>
                    ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {onLoadMore && (
        <LoadMore
          onLoadMore={onLoadMore}
          hasMore={hasMore}
          loading={loadingMore}
          total={total}
          loaded={rows.length}
        />
      )}
    </div>
  );
}
