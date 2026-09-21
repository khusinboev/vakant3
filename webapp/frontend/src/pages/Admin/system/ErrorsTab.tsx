import { useMemo, useState } from "react";

import { getErrorLog } from "../../../api/admin";
import type { ErrorLogItem, ErrorLogSource } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import type { TranslationKey } from "../../../i18n";
import DataTable, { type Column } from "../components/DataTable";
import FilterBar from "../components/FilterBar";
import { useCursorQuery } from "../hooks/useCursorQuery";
import JsonDetails from "./JsonDetails";

const PAGE_LIMIT = 30;

const SOURCE_LABEL: Record<ErrorLogSource, TranslationKey> = {
  api: "adminSystem.errors.source.api",
  bot: "adminSystem.errors.source.bot",
  scheduler: "adminSystem.errors.source.scheduler",
};

const LEVEL_CLASS: Record<string, string> = {
  error: "bg-danger/10 text-danger",
  warning: "bg-warning/10 text-warning",
  info: "bg-surfaceAlt text-muted",
};

/** `error_log` browser — filterable by source, newest first. */
export default function ErrorsTab() {
  const t = useT();
  const { formatDateTime } = useLocale();
  const [source, setSource] = useState<ErrorLogSource | "">("");

  const query = useMemo(
    () => ({ source: (source || undefined) as ErrorLogSource | undefined, limit: PAGE_LIMIT }),
    [source],
  );

  const errors = useCursorQuery<ErrorLogItem>(
    ["admin", "errors", query],
    (cursor) => getErrorLog({ ...query, cursor: cursor ?? undefined }),
  );

  const columns: Column<ErrorLogItem>[] = [
    {
      key: "created_at",
      labelKey: "adminSystem.errors.col.time",
      render: (row) => formatDateTime(row.created_at),
    },
    {
      key: "source",
      labelKey: "adminSystem.errors.col.source",
      render: (row) => (
        <span className="inline-flex rounded-full bg-surfaceAlt px-2 py-0.5 text-[11px] font-semibold text-muted">
          {t(SOURCE_LABEL[row.source])}
        </span>
      ),
    },
    {
      key: "level",
      labelKey: "adminSystem.errors.col.level",
      render: (row) => (
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
            LEVEL_CLASS[row.level] ?? LEVEL_CLASS.info
          }`}
        >
          {row.level}
        </span>
      ),
    },
    {
      key: "message",
      labelKey: "adminSystem.errors.col.message",
      render: (row) => <span className="line-clamp-2 max-w-sm">{row.message}</span>,
    },
    {
      key: "context",
      labelKey: "adminSystem.errors.col.context",
      render: (row) => <JsonDetails data={row.context} labelKey="adminSystem.errors.viewContext" />,
    },
  ];

  return (
    <div className="space-y-3">
      <FilterBar onReset={() => setSource("")}>
        <FilterBar.Select
          value={source}
          onChange={(value) => setSource(value as ErrorLogSource | "")}
          options={[
            { value: "api", labelKey: "adminSystem.errors.source.api" },
            { value: "bot", labelKey: "adminSystem.errors.source.bot" },
            { value: "scheduler", labelKey: "adminSystem.errors.source.scheduler" },
          ]}
          allKey="admin.filter.all"
          labelKey="adminSystem.errors.filterSource"
        />
      </FilterBar>

      <DataTable
        columns={columns}
        rows={errors.items}
        getRowId={(row) => row.id}
        loading={errors.isLoading}
        error={errors.error}
        onRetry={errors.refetch}
        hasMore={errors.hasMore}
        onLoadMore={errors.loadMore}
        loadingMore={errors.isFetchingMore}
        total={errors.total}
        captionKey="adminSystem.errors.title"
        stickyHeader
      />
    </div>
  );
}
