import { History } from "lucide-react";

import { getAutoPostHistory } from "../../../api/admin";
import type { AutoPostLogItem, AutoPostLogStatus } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import ErrorCard from "../components/ErrorCard";
import LoadMore from "../components/LoadMore";
import { useCursorQuery } from "../hooks/useCursorQuery";
import { StatusChip } from "../ui/Chip";
import EmptyState from "../ui/EmptyState";
import { FilterChips, useAdminFilters, type FilterDef } from "../ui/Filters";
import { List, ListRow } from "../ui/List";
import Skeleton from "../ui/Skeleton";
import { AUTO_POST_HISTORY_KEY } from "./historyKey";

const FILTERS: FilterDef[] = [
  {
    key: "status",
    labelKey: "adminAutopost.history.filter.status",
    type: "select",
    options: [
      { value: "sent", labelKey: "adminAutopost.status.sent" },
      { value: "failed", labelKey: "adminAutopost.status.failed" },
      { value: "skipped", labelKey: "adminAutopost.status.skipped" },
    ],
  },
];

/** Every auto-post attempt (`GET /admin/auto-post/history`), cursor-paginated, filterable by status. */
export default function AutoPostHistory() {
  const t = useT();
  const locale = useLocale();
  const filters = useAdminFilters(FILTERS, "autopost.history.filters");
  const status = (filters.values.status as AutoPostLogStatus | undefined) || undefined;

  const history = useCursorQuery<AutoPostLogItem>(
    [...AUTO_POST_HISTORY_KEY, status ?? null],
    (cursor) => getAutoPostHistory({ cursor: cursor ?? undefined, status }),
  );

  return (
    <section className="space-y-2">
      <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">
        {t("adminAutopost.history.title")}
      </h2>
      <FilterChips defs={FILTERS} state={filters} />

      {history.isLoading ? (
        <Skeleton rows={4} />
      ) : history.error ? (
        <ErrorCard error={history.error} onRetry={history.refetch} />
      ) : history.items.length === 0 ? (
        <EmptyState icon={History} labelKey="adminAutopost.history.empty" />
      ) : (
        <List>
          {history.items.map((row) => (
            <ListRow
              key={row.id}
              title={row.uid ?? "—"}
              subtitle={
                <>
                  {row.channel ?? "—"} · {locale.formatDateTime(row.posted_at)}
                  {row.error && <span className="text-danger"> · {row.error}</span>}
                </>
              }
              trailing={<StatusChip status={row.status} labelKey={`adminAutopost.status.${row.status}`} />}
            />
          ))}
        </List>
      )}

      <LoadMore
        onLoadMore={history.loadMore}
        hasMore={history.hasMore}
        loading={history.isFetchingMore}
        total={history.total}
        loaded={history.items.length}
      />
    </section>
  );
}
