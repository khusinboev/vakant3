import { RefreshCw, Trash2 } from "lucide-react";

import useToast from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import useLocale from "../../../i18n/useLocale";
import type { Channel } from "../../../api/adminTypes";
import { closeConfirm, requestConfirm } from "../hooks/useConfirm";
import { EmptyState, List, ListRow, Skeleton, StatusChip, Toolbar, type Tone } from "../ui";
import ErrorCard from "../components/ErrorCard";
import { useCheckChannel, useChannelsQuery, useDeleteChannel, useSetChannelEnabled } from "./useChannels";

function channelHandle(channel: Channel): string {
  return channel.username ? `@${channel.username}` : channel.invite_link || channel.id;
}

/** ok / fail / never-checked, as a single compact chip (spec §4 trailing). */
function statusChipProps(channel: Channel): {
  status: string;
  tone: Tone;
  labelKey: "adminChannels.chip.ok" | "adminChannels.chip.fail" | "adminChannels.chip.unknown";
} {
  if (channel.last_check_at == null) {
    return { status: "unknown", tone: "neutral", labelKey: "adminChannels.chip.unknown" };
  }
  return channel.last_check_ok
    ? { status: "ok", tone: "success", labelKey: "adminChannels.chip.ok" }
    : { status: "failed", tone: "danger", labelKey: "adminChannels.chip.fail" };
}

/** 32×18 on/off switch — the kit has no dedicated Switch, so this stays local to the row. */
function EnabledSwitch({
  checked,
  disabled,
  ariaLabel,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  ariaLabel: string;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onChange}
      className={`relative inline-flex h-[18px] w-8 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
        checked ? "bg-success" : "bg-border"
      }`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-surface shadow transition-transform ${
          checked ? "translate-x-[15px]" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

/**
 * The gate's channel list (spec §4/§4b): a dense `List`, one row per channel —
 * title/@username, last-check time as the subtitle, and a trailing cluster of
 * status chip + enabled switch + a per-row `Toolbar` that folds check-now/
 * delete behind a single ⋯ on phones instead of an always-visible cluster.
 */
export default function ChannelsList() {
  const t = useT();
  const toast = useToast();
  const { formatDateTime } = useLocale();
  const query = useChannelsQuery();
  const setEnabled = useSetChannelEnabled();
  const check = useCheckChannel();
  const remove = useDeleteChannel();

  const runCheck = (channel: Channel) => {
    check.mutate(channel.id, {
      onSuccess: (result) => {
        if (result.ok) toast.success(t("adminChannels.check.ok"));
        else toast.error(t("adminChannels.check.failed"));
      },
      onError: (error) => toast.apiError(error),
    });
  };

  const toggleEnabled = (channel: Channel) => {
    setEnabled.mutate(
      { id: channel.id, enabled: !channel.enabled },
      { onError: (error) => toast.apiError(error) },
    );
  };

  const confirmDelete = async (channel: Channel) => {
    const name = channel.title || channelHandle(channel);
    const ok = await requestConfirm({
      titleKey: "adminChannels.delete.title",
      descriptionKey: "adminChannels.delete.description",
      descriptionVars: { name },
      danger: true,
      confirmLabelKey: "common.delete",
    });
    if (!ok) return;
    try {
      await remove.mutateAsync(channel.id);
      toast.success(t("adminChannels.delete.success"));
    } catch (error) {
      toast.apiError(error);
    } finally {
      closeConfirm();
    }
  };

  if (query.isPending) return <Skeleton rows={4} />;
  if (query.isError) return <ErrorCard error={query.error} onRetry={() => void query.refetch()} />;

  const channels = query.data?.items ?? [];
  if (channels.length === 0) return <EmptyState labelKey="adminChannels.empty" />;

  return (
    <List>
      {channels.map((channel) => {
        const handle = channelHandle(channel);
        const name = channel.title || handle;
        const chip = statusChipProps(channel);
        const when = channel.last_check_at != null ? formatDateTime(channel.last_check_at) : null;

        return (
          <ListRow
            key={channel.id}
            title={name}
            subtitle={when ?? t("adminChannels.status.never")}
            trailing={
              <div className="flex items-center gap-1.5">
                <StatusChip status={chip.status} tone={chip.tone} labelKey={chip.labelKey} />
                <EnabledSwitch
                  checked={channel.enabled}
                  disabled={setEnabled.isPending}
                  ariaLabel={t(channel.enabled ? "adminChannels.toggle.disable" : "adminChannels.toggle.enable", { name })}
                  onChange={() => toggleEnabled(channel)}
                />
                <Toolbar
                  name={`channels.row.${channel.id}`}
                  max={0}
                  items={[
                    {
                      id: "check",
                      label: t("adminChannels.action.check", { name }),
                      icon: RefreshCw,
                      disabled: check.isPending,
                      onClick: () => runCheck(channel),
                    },
                    {
                      id: "delete",
                      label: t("adminChannels.action.delete", { name }),
                      icon: Trash2,
                      danger: true,
                      onClick: () => void confirmDelete(channel),
                    },
                  ]}
                />
              </div>
            }
          />
        );
      })}
    </List>
  );
}
