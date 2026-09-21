import { useMemo, useState } from "react";
import { Megaphone, Plus, RefreshCw, StopCircle } from "lucide-react";

import { adminKeys, listBroadcasts } from "../../../api/admin";
import type { Broadcast } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import DataTable, { type Column } from "../components/DataTable";
import RoleGate from "../components/RoleGate";
import { useConfirmedMutation } from "../hooks/useConfirmedMutation";
import { useCursorQuery } from "../hooks/useCursorQuery";
import BroadcastDetailSheet from "../broadcasts/BroadcastDetail";
import Composer from "../broadcasts/Composer";
import ProgressBar from "../broadcasts/ProgressBar";
import StatusChip from "../broadcasts/StatusChip";
import { cancelBroadcastWithToken } from "../broadcasts/api";
import { KIND_LABEL_KEY } from "../broadcasts/labels";

/** Statuses the bot worker is still touching — they make the list poll. */
const ACTIVE_STATUSES = new Set(["queued", "running"]);
const CANCELLABLE = new Set(["draft", "queued", "running", "paused"]);
const POLL_MS = 5000;

type Tab = "list" | "compose";

/**
 * Broadcasts: the list of jobs with live counters, and the composer.
 *
 * The list polls every 5 s only while something is queued or running — a
 * finished job never changes, and the admin panel is opened inside Telegram
 * on phone data.
 */
export default function BroadcastsPage() {
  const t = useT();
  const { formatDateTime } = useLocale();
  const [tab, setTab] = useState<Tab>("list");
  const [openId, setOpenId] = useState<number | null>(null);

  const [anyActive, setAnyActive] = useState(false);
  const broadcasts = useCursorQuery<Broadcast>(
    adminKeys.broadcasts(),
    (cursor) => listBroadcasts({ limit: 20, cursor: cursor ?? undefined }),
    { refetchInterval: anyActive ? POLL_MS : false },
  );

  const items = broadcasts.items;
  const active = useMemo(() => items.some((row) => ACTIVE_STATUSES.has(row.status)), [items]);
  if (active !== anyActive) setAnyActive(active);

  const cancel = useConfirmedMutation<{ id: number }, { id: number; status: string }>({
    action: "broadcast.cancel",
    paramKeys: ["id"],
    danger: true,
    titleKey: "adminBroadcasts.confirm.cancelTitle",
    descriptionKey: "adminBroadcasts.confirm.cancelDesc",
    confirmLabelKey: "adminBroadcasts.action.cancel",
    successKey: "adminBroadcasts.ok.cancelled",
    invalidate: [["admin", "broadcasts"]],
    mutationFn: (body, token) => cancelBroadcastWithToken(body.id, token),
  });

  const cancelRow = (row: Broadcast) =>
    cancel.run({ id: row.id }, { id: row.id }, { id: row.id });

  const columns: Column<Broadcast>[] = [
    {
      key: "id",
      labelKey: "adminBroadcasts.col.id",
      className: "w-16",
      render: (row) => <span className="tabular-nums text-muted">#{row.id}</span>,
    },
    {
      key: "status",
      labelKey: "adminBroadcasts.col.status",
      render: (row) => <StatusChip status={row.status} />,
    },
    {
      key: "kind",
      labelKey: "adminBroadcasts.col.kind",
      hideOnCard: true,
      render: (row) => <span className="text-muted">{t(KIND_LABEL_KEY[row.kind])}</span>,
    },
    {
      key: "segment",
      labelKey: "adminBroadcasts.col.segment",
      hideOnCard: true,
      render: (row) => (
        <span className="rounded-full bg-surfaceAlt px-2 py-0.5 text-xs text-muted">
          {row.target?.segment ?? "all"}
        </span>
      ),
    },
    {
      key: "progress",
      labelKey: "adminBroadcasts.col.progress",
      render: (row) => (
        <ProgressBar sent={row.sent} failed={row.failed} blocked={row.blocked} total={row.total} />
      ),
    },
    {
      key: "created_at",
      labelKey: "adminBroadcasts.col.created",
      align: "right",
      hideOnCard: true,
      render: (row) => (
        <span className="whitespace-nowrap text-xs text-muted">
          {row.created_at ? formatDateTime(row.created_at) : "—"}
        </span>
      ),
    },
  ];

  const openRow = items.find((row) => row.id === openId) ?? null;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text">{t("adminBroadcasts.title")}</h1>
          <p className="text-sm text-muted">{t("adminBroadcasts.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          {anyActive && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs text-primary">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />
              {t("adminBroadcasts.live")}
            </span>
          )}
          <button
            type="button"
            onClick={() => broadcasts.refetch()}
            aria-label={t("adminBroadcasts.refresh")}
            className="rounded-xl border border-border p-2 text-muted hover:bg-surfaceAlt hover:text-text focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            <RefreshCw size={15} aria-hidden="true" />
          </button>
        </div>
      </header>

      <div role="tablist" aria-label={t("adminBroadcasts.title")} className="flex gap-1 rounded-xl bg-surfaceAlt p-1">
        {(["list", "compose"] as Tab[]).map((id) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`flex-1 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40 ${
              tab === id ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text"
            }`}
          >
            <span className="inline-flex items-center justify-center gap-1.5">
              {id === "compose" ? <Plus size={14} aria-hidden="true" /> : null}
              {t(id === "list" ? "adminBroadcasts.tab.list" : "adminBroadcasts.tab.compose")}
            </span>
          </button>
        ))}
      </div>

      {tab === "compose" ? (
        <RoleGate min="admin" mode="disable">
          <Composer onQueued={broadcasts.refetch} />
        </RoleGate>
      ) : (
        <DataTable
          columns={columns}
          rows={items}
          getRowId={(row) => row.id}
          loading={broadcasts.isLoading}
          error={broadcasts.error}
          onRetry={broadcasts.refetch}
          hasMore={broadcasts.hasMore}
          onLoadMore={broadcasts.loadMore}
          loadingMore={broadcasts.isFetchingMore}
          total={broadcasts.total}
          onRowClick={(row) => setOpenId(row.id)}
          captionKey="adminBroadcasts.list.caption"
          emptyKey="adminBroadcasts.list.empty"
          emptyIcon={Megaphone}
        />
      )}

      <BroadcastDetailSheet
        broadcastId={openId}
        onClose={() => setOpenId(null)}
        actions={
          openRow && CANCELLABLE.has(openRow.status) ? (
            <RoleGate min="admin" mode="disable">
              <button
                type="button"
                onClick={() => void cancelRow(openRow)}
                disabled={cancel.isPending}
                className="inline-flex items-center gap-1.5 rounded-xl bg-danger px-3.5 py-2 text-sm font-semibold text-primaryFg disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                <StopCircle size={15} aria-hidden="true" />
                {t("adminBroadcasts.action.cancel")}
              </button>
            </RoleGate>
          ) : null
        }
      />
    </div>
  );
}
