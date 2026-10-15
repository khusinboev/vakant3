import { useQuery } from "@tanstack/react-query";
import { Pause, Play, StopCircle } from "lucide-react";

import { adminKeys } from "../../../api/admin";
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
  type KeyValueRow,
} from "../ui";
import MessagePreview from "./MessagePreview";
import {
  CONTENT_REJECTED,
  ERROR_KINDS,
  cancelBroadcastWithToken,
  getBroadcastDetail,
  setBroadcastStateWithToken,
  type BroadcastDetailFull,
  type BroadcastStateResult,
} from "./api";
import {
  ACTIVE_STATUSES,
  CANCELLABLE,
  ERROR_KIND_LABEL_KEY,
  PAUSABLE,
  RESUMABLE,
  errorKindLabelKey,
  statusLabelKey,
  statusToneOf,
} from "./labels";
import { SEGMENT_LABEL_KEY, parseSegment } from "./segments";
import { checkTelegramHtml } from "./telegramHtml";

export type BroadcastDetailPageProps = { id: number };

/**
 * `/admin/broadcasts/:id` — the live job: four counters, the progress bar,
 * failures by kind, retry state, the message that went out and the last 20
 * per-user errors. Pause / Resume is the header's primary action (whichever
 * the status allows); Cancel sits in the ⋯ menu (danger). Each goes through
 * the shared, history-backed confirm dialog with haptic feedback.
 */
export default function BroadcastDetailPage({ id }: BroadcastDetailPageProps) {
  const t = useT();
  const { formatDateTime, formatNumber } = useLocale();

  const query = useQuery<BroadcastDetailFull>({
    queryKey: adminKeys.broadcastDetail(id),
    queryFn: () => getBroadcastDetail(id),
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

  const pause = useConfirmedMutation<{ id: number }, BroadcastStateResult>({
    action: "broadcast.pause",
    paramKeys: ["id"],
    titleKey: "adminBroadcasts.confirm.pauseTitle",
    descriptionKey: "adminBroadcasts.confirm.pauseDesc",
    confirmLabelKey: "adminBroadcasts.action.pause",
    successKey: "adminBroadcasts.ok.paused",
    invalidate: [["admin", "broadcasts"]],
    mutationFn: (payload, token) => setBroadcastStateWithToken(payload.id, "pause", token),
  });

  const resume = useConfirmedMutation<{ id: number }, BroadcastStateResult>({
    action: "broadcast.resume",
    paramKeys: ["id"],
    titleKey: "adminBroadcasts.confirm.resumeTitle",
    descriptionKey: "adminBroadcasts.confirm.resumeDesc",
    confirmLabelKey: "adminBroadcasts.action.resume",
    successKey: "adminBroadcasts.ok.resumed",
    invalidate: [["admin", "broadcasts"]],
    mutationFn: (payload, token) => setBroadcastStateWithToken(payload.id, "resume", token),
  });

  const busy = cancel.isPending || pause.isPending || resume.isPending;
  const canPause = Boolean(job && PAUSABLE.has(job.status));
  const canResume = Boolean(job && RESUMABLE.has(job.status));

  useAdminHeader({
    title: t("adminBroadcasts.detail.title", { id }),
    primary: canPause
      ? {
          labelKey: "adminBroadcasts.action.pause",
          icon: Pause,
          disabled: busy,
          loading: pause.isPending,
          onClick: () => void pause.run({ id }, { id }, { id }),
        }
      : canResume
        ? {
            labelKey: "adminBroadcasts.action.resume",
            icon: Play,
            disabled: busy,
            loading: resume.isPending,
            onClick: () => void resume.run({ id }, { id }, { id }),
          }
        : undefined,
    menu: [
      {
        labelKey: "adminBroadcasts.action.cancel",
        icon: StopCircle,
        danger: true,
        disabled: busy,
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

  const kindCounts = job.error_kinds ?? {};
  const kindRows: KeyValueRow[] = ERROR_KINDS.map((kind) => ({
    labelKey: ERROR_KIND_LABEL_KEY[kind],
    value: formatNumber(kindCounts[kind] ?? 0),
    tone: kind === "bad_request" || kind === "other" ? "danger" : undefined,
    hidden: !kindCounts[kind],
  }));
  const retry = job.retry;
  const retryRows: KeyValueRow[] = retry
    ? [
        { labelKey: "adminBroadcasts.retry.scheduled", value: formatNumber(retry.scheduled), tone: retry.scheduled ? "warning" : undefined },
        {
          labelKey: "adminBroadcasts.retry.nextAt",
          value: retry.next_attempt_at ? formatDateTime(retry.next_attempt_at) : "—",
          hidden: !retry.next_attempt_at,
        },
        { labelKey: "adminBroadcasts.retry.retried", value: formatNumber(retry.retried) },
        { labelKey: "adminBroadcasts.retry.extra", value: formatNumber(retry.extra_attempts) },
      ]
    : [];
  const hasRetries = Boolean(retry && (retry.scheduled || retry.retried));

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
          {job.error === CONTENT_REJECTED
            ? t("adminBroadcasts.detail.contentRejected")
            : t("adminBroadcasts.detail.lastError", { error: job.error })}
        </p>
      )}

      <KeyValue
        rows={[
          { labelKey: "adminBroadcasts.detail.created", value: job.created_at ? formatDateTime(job.created_at) : "—" },
          { labelKey: "adminBroadcasts.detail.started", value: job.started_at ? formatDateTime(job.started_at) : "—" },
          { labelKey: "adminBroadcasts.detail.finished", value: job.finished_at ? formatDateTime(job.finished_at) : "—" },
        ]}
      />

      {kindRows.some((row) => !row.hidden) && (
        <>
          <p className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
            {t("adminBroadcasts.detail.errorKinds")}
          </p>
          <KeyValue rows={kindRows} />
        </>
      )}

      {hasRetries && (
        <>
          <p className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
            {t("adminBroadcasts.detail.retry")}
          </p>
          <KeyValue rows={retryRows} />
        </>
      )}

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
              subtitle={`${t(errorKindLabelKey(row.error_kind ?? (row.status === "blocked" ? "blocked" : "other")))}${
                row.error ? ` · ${row.error}` : ""
              }`}
              meta={
                row.attempts > 1
                  ? t("adminBroadcasts.detail.attempts", { count: formatNumber(row.attempts) })
                  : row.sent_at
                    ? formatDateTime(row.sent_at)
                    : undefined
              }
            />
          ))}
        </List>
      )}
    </div>
  );
}
