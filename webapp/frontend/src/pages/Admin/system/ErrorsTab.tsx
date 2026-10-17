import { useMemo } from "react";

import { getErrorLog } from "../../../api/admin";
import type { ErrorLogItem, ErrorLogSource } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import ErrorCard from "../components/ErrorCard";
import LoadMore from "../components/LoadMore";
import { useCursorQuery } from "../hooks/useCursorQuery";
import { useHistorySheet } from "../hooks/useHistorySheet";
import {
  EmptyState,
  FilterChips,
  JsonDetails,
  List,
  ListRow,
  Sheet,
  Skeleton,
  StatusChip,
  useAdminFilters,
  type FilterDef,
  type Tone,
} from "../ui";

const PAGE_LIMIT = 30;
const DETAIL_SHEET = "system.errors.detail";

const LEVEL_TONE: Record<string, Tone> = { error: "danger", warning: "warning", info: "neutral" };

const FILTERS: FilterDef[] = [
  {
    key: "source",
    labelKey: "adminSystem.errors.filterSource",
    type: "select",
    options: [
      { value: "api", labelKey: "adminSystem.errors.source.api" },
      { value: "bot", labelKey: "adminSystem.errors.source.bot" },
      { value: "scheduler", labelKey: "adminSystem.errors.source.scheduler" },
    ],
  },
  {
    key: "level",
    labelKey: "adminSystem.errors.filterLevel",
    type: "select",
    options: [
      { value: "error", labelKey: "adminSystem.errors.level.error" },
      { value: "warning", labelKey: "adminSystem.errors.level.warning" },
      { value: "info", labelKey: "adminSystem.errors.level.info" },
    ],
  },
];

/** `error_log` browser — filterable by source (server-side) and level (client-side: `admin_system.py` only filters on `source`). */
export default function ErrorsTab() {
  const { formatDateTime } = useLocale();
  const filters = useAdminFilters(FILTERS, "system.errors.filters");
  const detail = useHistorySheet<ErrorLogItem>(DETAIL_SHEET);

  const source = (filters.values.source || undefined) as ErrorLogSource | undefined;
  const level = filters.values.level || undefined;

  const query = useMemo(() => ({ source, limit: PAGE_LIMIT }), [source]);

  const errors = useCursorQuery<ErrorLogItem>(["admin", "errors", query], (cursor) =>
    getErrorLog({ ...query, cursor: cursor ?? undefined }),
  );

  const items = useMemo(
    () => (level ? errors.items.filter((row) => row.level === level) : errors.items),
    [errors.items, level],
  );

  return (
    <div className="space-y-2">
      <FilterChips defs={FILTERS} state={filters} />

      {errors.isLoading && <Skeleton rows={5} />}
      {Boolean(errors.error) && <ErrorCard error={errors.error} onRetry={errors.refetch} />}
      {!errors.isLoading &&
        !errors.error &&
        (items.length === 0 ? (
          <EmptyState labelKey="admin.table.empty" />
        ) : (
          <List>
            {items.map((row) => (
              <ListRow
                key={row.id}
                title={<span className="line-clamp-1">{row.message}</span>}
                subtitle={row.source}
                meta={formatDateTime(row.created_at)}
                trailing={<StatusChip status={row.level} tone={LEVEL_TONE[row.level]} />}
                onClick={() => detail.openSheet(row)}
              />
            ))}
          </List>
        ))}

      <LoadMore
        hasMore={errors.hasMore}
        onLoadMore={errors.loadMore}
        loading={errors.isFetchingMore}
        total={errors.total}
        loaded={errors.items.length}
      />

      <Sheet name={DETAIL_SHEET} titleKey="adminSystem.errors.detailTitle">
        {detail.payload && (
          <div className="space-y-2">
            <p className="text-[11px] text-muted">
              {formatDateTime(detail.payload.created_at)} · {detail.payload.source} · {detail.payload.level}
            </p>
            <p className="text-[13px] text-text">{detail.payload.message}</p>
            <JsonDetails data={detail.payload.context} labelKey="adminSystem.errors.viewContext" />
          </div>
        )}
      </Sheet>
    </div>
  );
}
