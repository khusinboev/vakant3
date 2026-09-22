import { useQuery } from "@tanstack/react-query";
import { StopCircle } from "lucide-react";

import { adminKeys, getBroadcast } from "../../../api/admin";
import type { BroadcastDetail } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import ErrorCard from "../components/ErrorCard";
import { useConfirmedMutation } from "../hooks/useConfirmedMutation";
import {
  Accordion,
  KeyValue,
  List,
  ListRow,
  ProgressBar,
  Skeleton,
  StatTile,
  StatusChip,
  useAdminHeader,
} from "../ui";
import MessagePreview from "./MessagePreview";
import { cancelBroadcastWithToken } from "./api";
import { ACTIVE_STATUSES, CANCELLABLE, statusLabelKey, statusToneOf } from "./labels";
import { SEGMENT_LABEL_KEY, parseSegment } from "./segments";
import { checkTelegramHtml } from "./telegramHtml";

export type BroadcastDetailPageProps = { id: number };

/**
 * `/admin/broadcasts/:id` — the live job: four counters, the progress bar, the
 * message that went out and the last 20 per-user errors. Cancel sits in the
 * header's ⋯ menu (danger, confirm token `broadcast.cancel`).
 */
export default function BroadcastDetailPage({ id }: BroadcastDetailPageProps) {
  const t = useT();
  const { formatDateTime, formatNumber } = useLocale();

  const query = useQuery<BroadcastDetail>({
    queryKey: adminKeys.broadcastDetail(id),
    queryFn: () => getBroadcast(id),
    retry: false,
    // A running job's counters move; a finished one never changes again.
    refetchInterval: (entry) =>
      ACTIVE_STATUSES.has(entry.state.data?.status ?? "") ? 5000 : false,
  });

  const job = query.data;

  const cancel = useConfirmedMutation<{ id: number }, { id: number; status: string }>({
    action: "broadcast.cancel",
    paramKeys: ["id"],
    danger: true,
    titleKey: "adminBroadcasts.confirm.cancelTitle",
    descriptionKey: "adminBroadcasts.confirm.cancelDesc",
    confirmLabelKey: "adminBroadcasts.action.cancel",
    successKey: "adminBroadcasts.ok.cancelled",
    invalidate: [["admin", "broadcasts"]],
    mutationFn: (payload, token) => cancelBroadcastWithToken(payload.id, token),
  });

  useAdminHeader({
    title: t("adminBroadcasts.detail.title", { id }),
    menu: [
      {
        labelKey: "adminBroadcasts.action.cancel",
        icon: StopCircle,
        danger: true,
        disabled: cancel.isPending,
        hidden: !job || !CANCELLABLE.has(job.status),
        onClick: () => void cancel.run({ id }, { id }, { id }),
      },
    ],
  });

  if (query.isError) {
    return <ErrorCard error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (!job) return <Skeleton rows={5} />;

  const done = job.sent + job.failed + job.blocked;
  const pending = Math.max(0, job.total - done);
  const parsed = parseSegment(job.target?.segment ?? "all");
  const segmentText = parsed.value
    ? `${t(SEGMENT_LABEL_KEY[parsed.kind])}: ${parsed.value}`
    : t(SEGMENT_LABEL_KEY[parsed.kind]);
  const preview = checkTelegramHtml(job.text ?? "");

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip
          status={job.status}
          tone={statusToneOf(job.status)}
          labelKey={statusLabelKey(job.status)}
        />
        <span className="truncate text-[11px] text-muted">{segmentText}</span>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <StatTile labelKey="adminBroadcasts.progress.sent" value={formatNumber(job.sent)} />
        <StatTile labelKey="adminBroadcasts.progress.failed" value={formatNumber(job.failed)} />
        <StatTile labelKey="adminBroadcasts.progress.blocked" value={formatNumber(job.blocked)} />
        <StatTile labelKey="adminBroadcasts.progress.pending" value={formatNumber(pending)} />
      </div>

      <div className="space-y-1">
        <ProgressBar
          value={done}
          max={job.total}
          tone={statusToneOf(job.status)}
          label={t("adminBroadcasts.progress.label", {
            sent: formatNumber(job.sent),
            total: formatNumber(job.total),
          })}
        />
        <p className="text-[11px] tabular-nums text-muted">
          {t("adminBroadcasts.progress.label", {
            sent: formatNumber(job.sent),
            total: formatNumber(job.total),
          })}
        </p>
      </div>

      {job.error && (
        <p role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-[11px] text-danger">
          {t("adminBroadcasts.detail.lastError", { error: job.error })}
        </p>
      )}

      <KeyValue
        rows={[
          { labelKey: "adminBroadcasts.detail.created", value: job.created_at ? formatDateTime(job.created_at) : "—" },
          { labelKey: "adminBroadcasts.detail.started", value: job.started_at ? formatDateTime(job.started_at) : "—" },
          { labelKey: "adminBroadcasts.detail.finished", value: job.finished_at ? formatDateTime(job.finished_at) : "—" },
        ]}
      />

      <Accordion
        queryKey="sec"
        items={[
          {
            id: "message",
            titleKey: "adminBroadcasts.detail.message",
            content: <MessagePreview html={preview.html} buttons={job.buttons} />,
          },
        ]}
      />

      <p className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {t("adminBroadcasts.detail.errors")}
      </p>
      {job.errors.length === 0 ? (
        <p className="text-[11px] text-muted">{t("adminBroadcasts.detail.noErrors")}</p>
      ) : (
        <List ariaLabelKey="adminBroadcasts.detail.errors">
          {job.errors.map((row) => (
            <ListRow
              key={`${row.user_id}-${row.sent_at ?? 0}`}
              title={String(row.user_id)}
              subtitle={row.error || row.status}
              meta={row.sent_at ? formatDateTime(row.sent_at) : undefined}
            />
          ))}
        </List>
      )}
    </div>
  );
}
