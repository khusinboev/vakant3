import { useState } from "react";
import { CheckCircle2, Radio, RefreshCw, Trash2, XCircle } from "lucide-react";

import useToast from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import useLocale from "../../../i18n/useLocale";
import type { Channel } from "../../../api/adminTypes";
import ConfirmDialog from "../components/ConfirmDialog";
import DataTable, { type Column } from "../components/DataTable";
import ToggleRow from "../components/ToggleRow";
import { useCheckChannel, useChannelsQuery, useDeleteChannel, useSetChannelEnabled } from "./useChannels";

function channelHandle(channel: Channel): string {
  return channel.username ? `@${channel.username}` : channel.invite_link || channel.id;
}

function ChannelIdentity({ channel }: { channel: Channel }) {
  const handle = channelHandle(channel);
  return (
    <div className="min-w-0">
      <p className="truncate text-sm font-semibold text-text">{channel.title || handle}</p>
      {channel.title && <p className="truncate text-xs text-muted">{handle}</p>}
    </div>
  );
}

function CheckStatus({ channel }: { channel: Channel }) {
  const t = useT();
  const { formatDateTime } = useLocale();
  if (channel.last_check_at == null) {
    return <span className="text-xs text-muted">{t("adminChannels.status.never")}</span>;
  }
  const when = formatDateTime(channel.last_check_at);
  if (channel.last_check_ok) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-success">
        <CheckCircle2 size={13} aria-hidden="true" />
        {t("adminChannels.status.ok", { time: when })}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-danger">
      <XCircle size={13} aria-hidden="true" />
      {t("adminChannels.status.failed", { time: when })}
    </span>
  );
}

/** The list of gate channels: table on tablet/desktop, cards on phones. */
export default function ChannelsList() {
  const t = useT();
  const toast = useToast();
  const query = useChannelsQuery();
  const setEnabled = useSetChannelEnabled();
  const check = useCheckChannel();
  const remove = useDeleteChannel();
  const [pendingDelete, setPendingDelete] = useState<Channel | null>(null);

  const runCheck = (row: Channel) => {
    check.mutate(row.id, {
      onSuccess: (result) => {
        if (result.ok) toast.success(t("adminChannels.check.ok"));
        else toast.error(t("adminChannels.check.failed"));
      },
      onError: (error) => toast.apiError(error),
    });
  };

  const toggleEnabled = (row: Channel, value: boolean) => {
    setEnabled.mutate(
      { id: row.id, enabled: value },
      { onError: (error) => toast.apiError(error) },
    );
  };

  const actions = (row: Channel) => (
    <div className="flex shrink-0 items-center gap-1">
      <button
        type="button"
        aria-label={t("adminChannels.action.check", { name: row.title || channelHandle(row) })}
        disabled={check.isPending}
        onClick={() => runCheck(row)}
        className="tap-target rounded-full p-2 text-muted hover:bg-surfaceAlt hover:text-text disabled:opacity-50"
      >
        <RefreshCw size={15} aria-hidden="true" />
      </button>
      <button
        type="button"
        aria-label={t("adminChannels.action.delete", { name: row.title || channelHandle(row) })}
        onClick={() => setPendingDelete(row)}
        className="tap-target rounded-full p-2 text-muted hover:bg-danger/10 hover:text-danger"
      >
        <Trash2 size={15} aria-hidden="true" />
      </button>
    </div>
  );

  const columns: Column<Channel>[] = [
    {
      key: "channel",
      labelKey: "adminChannels.column.channel",
      render: (row) => <ChannelIdentity channel={row} />,
    },
    {
      key: "status",
      labelKey: "adminChannels.column.status",
      render: (row) => <CheckStatus channel={row} />,
    },
    {
      key: "enabled",
      labelKey: "adminChannels.column.enabled",
      render: (row) => (
        <ToggleRow
          label={t(row.enabled ? "adminChannels.status.enabled" : "adminChannels.status.disabled")}
          checked={row.enabled}
          disabled={setEnabled.isPending}
          onChange={(value) => toggleEnabled(row, value)}
        />
      ),
    },
    {
      key: "actions",
      labelKey: "adminChannels.column.actions",
      align: "right",
      hideOnCard: true,
      render: actions,
    },
  ];

  return (
    <>
      <DataTable<Channel>
        columns={columns}
        rows={query.data?.items ?? []}
        getRowId={(row) => row.id}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyKey="adminChannels.empty"
        emptyIcon={Radio}
        captionKey="adminChannels.table.caption"
        renderCard={(row) => (
          <div className="space-y-2.5">
            <div className="flex items-start justify-between gap-2">
              <ChannelIdentity channel={row} />
              {actions(row)}
            </div>
            <CheckStatus channel={row} />
            <ToggleRow
              label={t(row.enabled ? "adminChannels.status.enabled" : "adminChannels.status.disabled")}
              checked={row.enabled}
              disabled={setEnabled.isPending}
              onChange={(value) => toggleEnabled(row, value)}
            />
          </div>
        )}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        titleKey="adminChannels.delete.title"
        descriptionKey="adminChannels.delete.description"
        descriptionVars={
          pendingDelete ? { name: pendingDelete.title || channelHandle(pendingDelete) } : undefined
        }
        danger
        confirmLabelKey="common.delete"
        loading={remove.isPending}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) return;
          remove.mutate(pendingDelete.id, {
            onSuccess: () => {
              toast.success(t("adminChannels.delete.success"));
              setPendingDelete(null);
            },
            onError: (error) => {
              toast.apiError(error);
              setPendingDelete(null);
            },
          });
        }}
      />
    </>
  );
}
