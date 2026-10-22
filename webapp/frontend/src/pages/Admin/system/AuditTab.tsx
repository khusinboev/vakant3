import { useMemo } from "react";

import { getAuditLog } from "../../../api/admin";
import type { AuditLogItem } from "../../../api/adminTypes";
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
  useAdminFilters,
  type FilterDef,
} from "../ui";

const PAGE_LIMIT = 30;
const DETAIL_SHEET = "system.audit.detail";

const FILTERS: FilterDef[] = [
  {
    key: "actor",
    labelKey: "adminSystem.audit.filterActorLabel",
    type: "text",
    placeholderKey: "adminSystem.audit.filterActorPlaceholder",
  },
  {
    key: "action",
    labelKey: "adminSystem.audit.filterActionLabel",
    type: "text",
    placeholderKey: "adminSystem.audit.filterActionPlaceholder",
  },
];

function targetOf(row: AuditLogItem): string | null {
  if (!row.target_type) return null;
  return row.target_id ? `${row.target_type}:${row.target_id}` : row.target_type;
}

/** `admin_audit_log` browser — filterable by actor id and an action-name prefix. */
export default function AuditTab() {
  const { formatDateTime } = useLocale();
  const filters = useAdminFilters(FILTERS, "system.audit.filters");
  const detail = useHistorySheet<AuditLogItem>(DETAIL_SHEET);

  const actorRaw = (filters.values.actor ?? "").trim();
  const actorId = /^\d+$/.test(actorRaw) ? Number(actorRaw) : undefined;
  const actionPrefix = (filters.values.action ?? "").trim() || undefined;

  const query = useMemo(() => ({ actor: actorId, action: actionPrefix, limit: PAGE_LIMIT }), [actorId, actionPrefix]);

  const audit = useCursorQuery<AuditLogItem>(["admin", "audit", query], (cursor) =>
    getAuditLog({ ...query, cursor: cursor ?? undefined }),
  );

  return (
    <div className="space-y-2">
      <FilterChips defs={FILTERS} state={filters} />

      {audit.isLoading && <Skeleton rows={5} />}
      {Boolean(audit.error) && <ErrorCard error={audit.error} onRetry={audit.refetch} />}
      {!audit.isLoading &&
        !audit.error &&
        (audit.items.length === 0 ? (
          <EmptyState labelKey="admin.table.empty" />
        ) : (
          <List>
            {audit.items.map((row) => (
              <ListRow
                key={row.id}
                title={<code className="text-[13px]">{row.action}</code>}
                subtitle={`#${row.actor_id}${targetOf(row) ? ` · ${targetOf(row)}` : ""}`}
                meta={formatDateTime(row.created_at)}
                onClick={() => detail.openSheet(row)}
              />
            ))}
          </List>
        ))}

      <LoadMore
        hasMore={audit.hasMore}
        onLoadMore={audit.loadMore}
        loading={audit.isFetchingMore}
        total={audit.total}
        loaded={audit.items.length}
      />

      <Sheet name={DETAIL_SHEET} titleKey="adminSystem.audit.detailTitle">
        {detail.payload && (
          <div className="space-y-2">
            <p className="text-[11px] text-muted">{formatDateTime(detail.payload.created_at)}</p>
            <p className="text-[13px] font-medium text-text">
              <code>{detail.payload.action}</code>
            </p>
            <p className="text-[11px] text-muted">
              #{detail.payload.actor_id}
              {targetOf(detail.payload) ? ` · ${targetOf(detail.payload)}` : ""}
              {detail.payload.ip ? ` · ${detail.payload.ip}` : ""}
            </p>
            <JsonDetails data={detail.payload.payload} labelKey="adminSystem.audit.viewPayload" />
          </div>
        )}
      </Sheet>
    </div>
  );
}
