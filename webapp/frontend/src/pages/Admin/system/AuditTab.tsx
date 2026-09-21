import { useMemo, useState } from "react";

import { getAuditLog } from "../../../api/admin";
import type { AuditLogItem } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import { useDebouncedValue } from "../../ResumeStudio/lib/useDebouncedValue";
import DataTable, { type Column } from "../components/DataTable";
import FilterBar from "../components/FilterBar";
import { useCursorQuery } from "../hooks/useCursorQuery";
import JsonDetails from "./JsonDetails";

const PAGE_LIMIT = 30;

/** `admin_audit_log` browser — filterable by actor id and an action-name prefix. */
export default function AuditTab() {
  const { formatDateTime } = useLocale();

  const [actorInput, setActorInput] = useState("");
  const [actionInput, setActionInput] = useState("");
  const actor = useDebouncedValue(actorInput, 350);
  const action = useDebouncedValue(actionInput, 350);

  const actorId = /^\d+$/.test(actor.trim()) ? Number(actor.trim()) : undefined;
  const actionPrefix = action.trim() || undefined;

  const query = useMemo(
    () => ({ actor: actorId, action: actionPrefix, limit: PAGE_LIMIT }),
    [actorId, actionPrefix],
  );

  const audit = useCursorQuery<AuditLogItem>(
    ["admin", "audit", query],
    (cursor) => getAuditLog({ ...query, cursor: cursor ?? undefined }),
  );

  const columns: Column<AuditLogItem>[] = [
    {
      key: "created_at",
      labelKey: "adminSystem.audit.col.time",
      render: (row) => formatDateTime(row.created_at),
    },
    { key: "actor_id", labelKey: "adminSystem.audit.col.actor" },
    {
      key: "action",
      labelKey: "adminSystem.audit.col.action",
      render: (row) => <code className="text-xs">{row.action}</code>,
    },
    {
      key: "target",
      labelKey: "adminSystem.audit.col.target",
      hideOnCard: true,
      render: (row) =>
        row.target_type ? `${row.target_type}${row.target_id ? `:${row.target_id}` : ""}` : "—",
    },
    {
      key: "payload",
      labelKey: "adminSystem.audit.col.payload",
      render: (row) => <JsonDetails data={row.payload} labelKey="adminSystem.audit.viewPayload" />,
    },
  ];

  return (
    <div className="space-y-3">
      <FilterBar
        onReset={() => {
          setActorInput("");
          setActionInput("");
        }}
      >
        <FilterBar.Search
          value={actorInput}
          onChange={setActorInput}
          placeholderKey="adminSystem.audit.filterActor"
        />
        <FilterBar.Search
          value={actionInput}
          onChange={setActionInput}
          placeholderKey="adminSystem.audit.filterAction"
        />
      </FilterBar>

      <DataTable
        columns={columns}
        rows={audit.items}
        getRowId={(row) => row.id}
        loading={audit.isLoading}
        error={audit.error}
        onRetry={audit.refetch}
        hasMore={audit.hasMore}
        onLoadMore={audit.loadMore}
        loadingMore={audit.isFetchingMore}
        total={audit.total}
        captionKey="adminSystem.audit.title"
        stickyHeader
      />
    </div>
  );
}
