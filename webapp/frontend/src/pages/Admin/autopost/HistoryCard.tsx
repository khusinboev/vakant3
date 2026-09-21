import { useState } from "react";
import { History } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { getAutoPostHistory } from "../../../api/admin";
import type { AutoPostLogItem, AutoPostLogStatus } from "../../../api/adminTypes";
import DataTable, { type Column } from "../components/DataTable";
import FilterBar from "../components/FilterBar";
import GroupCard from "../components/GroupCard";
import { useCursorQuery } from "../hooks/useCursorQuery";
import { AUTO_POST_HISTORY_KEY } from "./historyKey";
import StatusBadge, { type BadgeTone } from "./StatusBadge";

const STATUS_TONE: Record<AutoPostLogStatus, BadgeTone> = {
  sent: "success",
  failed: "danger",
  skipped: "muted",
};

const STATUS_OPTIONS: { value: AutoPostLogStatus; labelKey: "adminAutopost.status.sent" | "adminAutopost.status.failed" | "adminAutopost.status.skipped" }[] = [
  { value: "sent", labelKey: "adminAutopost.status.sent" },
  { value: "failed", labelKey: "adminAutopost.status.failed" },
  { value: "skipped", labelKey: "adminAutopost.status.skipped" },
];

/** Every auto-post attempt (`GET /admin/auto-post/history`), cursor-paginated, filterable by status. */
export default function HistoryCard() {
  const t = useT();
  const locale = useLocale();
  const [status, setStatus] = useState<AutoPostLogStatus | "">("");

  const history = useCursorQuery<AutoPostLogItem>(
    [...AUTO_POST_HISTORY_KEY, status || null],
    (cursor) => getAutoPostHistory({ cursor: cursor ?? undefined, status: status || undefined }),
  );

  const columns: Column<AutoPostLogItem>[] = [
    {
      key: "uid",
      labelKey: "adminAutopost.history.col.uid",
      render: (row) => row.uid ?? "—",
    },
    {
      key: "channel",
      labelKey: "adminAutopost.history.col.channel",
      render: (row) => row.channel ?? "—",
    },
    {
      key: "status",
      labelKey: "adminAutopost.history.col.status",
      render: (row) => <StatusBadge tone={STATUS_TONE[row.status]} labelKey={`adminAutopost.status.${row.status}`} />,
    },
    {
      key: "error",
      labelKey: "adminAutopost.history.col.error",
      render: (row) => (row.error ? <span className="text-danger">{row.error}</span> : "—"),
      hideOnCard: true,
    },
    {
      key: "posted_at",
      labelKey: "adminAutopost.history.col.time",
      render: (row) => locale.formatDateTime(row.posted_at),
      align: "right",
    },
  ];

  return (
    <GroupCard icon={History} title={t("adminAutopost.history.title")} divide={false}>
      <div className="space-y-3 py-3">
        <FilterBar onReset={status ? () => setStatus("") : undefined}>
          <FilterBar.Select
            value={status}
            onChange={(value) => setStatus(value as AutoPostLogStatus | "")}
            options={STATUS_OPTIONS}
            allKey="adminAutopost.history.filter.all"
            labelKey="adminAutopost.history.filter.status"
          />
        </FilterBar>

        <DataTable
          columns={columns}
          rows={history.items}
          getRowId={(row) => row.id}
          loading={history.isLoading}
          error={history.error}
          onRetry={history.refetch}
          emptyKey="adminAutopost.history.empty"
          emptyIcon={History}
          onLoadMore={history.loadMore}
          hasMore={history.hasMore}
          loadingMore={history.isFetchingMore}
          total={history.total}
          captionKey="adminAutopost.history.title"
        />
      </div>
    </GroupCard>
  );
}
