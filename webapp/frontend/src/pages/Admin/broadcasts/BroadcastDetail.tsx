import { useQuery } from "@tanstack/react-query";

import { adminKeys, getBroadcast } from "../../../api/admin";
import type { BroadcastDetail } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import BottomSheet from "../../../components/ui/BottomSheet";
import ErrorCard from "../components/ErrorCard";
import ProgressBar from "./ProgressBar";
import StatusChip from "./StatusChip";
import { checkTelegramHtml } from "./telegramHtml";

export type BroadcastDetailProps = {
  broadcastId: number | null;
  onClose: () => void;
  /** Rendered in the footer (the cancel button, role-gated by the page). */
  actions?: React.ReactNode;
};

const ACTIVE = new Set(["queued", "running"]);

/** Counters, the rendered message and the last 20 per-user errors. */
export default function BroadcastDetailSheet({ broadcastId, onClose, actions }: BroadcastDetailProps) {
  const t = useT();
  const { formatDateTime } = useLocale();

  const query = useQuery<BroadcastDetail>({
    queryKey: adminKeys.broadcastDetail(broadcastId ?? 0),
    queryFn: () => getBroadcast(broadcastId as number),
    enabled: broadcastId !== null,
    retry: false,
    // A running job's counters move; a finished one never changes again.
    refetchInterval: (query) => (ACTIVE.has(query.state.data?.status ?? "") ? 5000 : false),
  });

  const job = query.data;
  const preview = job ? checkTelegramHtml(job.text ?? "") : null;

  return (
    <BottomSheet
      open={broadcastId !== null}
      onClose={onClose}
      title={t("adminBroadcasts.detail.title", { id: broadcastId ?? 0 })}
      footer={
        <div className="flex items-center justify-end gap-2">
          {actions}
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-border px-3.5 py-2 text-sm font-medium text-text hover:bg-surfaceAlt focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            {t("adminBroadcasts.detail.close")}
          </button>
        </div>
      }
    >
      {query.isError && <ErrorCard error={query.error} onRetry={() => void query.refetch()} />}

      {query.isLoading && (
        <div className="space-y-2" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-14 animate-pulse rounded-xl bg-surfaceAlt" />
          ))}
        </div>
      )}

      {job && (
        <div className="space-y-4 px-1 pb-2">
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip status={job.status} />
            <span className="rounded-full bg-surfaceAlt px-2 py-0.5 text-xs text-muted">
              {job.target?.segment ?? "all"}
            </span>
          </div>

          <section>
            <h3 className="mb-2 text-xs font-semibold text-muted">{t("adminBroadcasts.detail.counters")}</h3>
            <ProgressBar
              sent={job.sent}
              failed={job.failed}
              blocked={job.blocked}
              total={job.total}
              detailed
            />
          </section>

          {job.error && (
            <p role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-xs text-danger">
              {t("adminBroadcasts.detail.lastError", { error: job.error })}
            </p>
          )}

          <section>
            <h3 className="mb-2 text-xs font-semibold text-muted">{t("adminBroadcasts.detail.message")}</h3>
            <div className="rounded-xl border border-border bg-surfaceAlt p-3">
              {preview?.html ? (
                // Sanitized through the Telegram allowlist (telegramHtml.ts).
                <div
                  className="whitespace-pre-wrap break-words text-sm text-text [&_a]:text-primary [&_a]:underline"
                  dangerouslySetInnerHTML={{ __html: preview.html }}
                />
              ) : (
                <p className="text-sm text-muted">{t("adminBroadcasts.composer.previewEmpty")}</p>
              )}
              {job.buttons.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {job.buttons.map((button, index) => (
                    <div
                      key={index}
                      className="truncate rounded-lg bg-surface px-3 py-2 text-center text-sm font-medium text-primary"
                    >
                      {button.text}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <dl className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-3">
            <Meta label={t("adminBroadcasts.detail.created")} value={job.created_at ? formatDateTime(job.created_at) : "—"} />
            <Meta label={t("adminBroadcasts.detail.started")} value={job.started_at ? formatDateTime(job.started_at) : "—"} />
            <Meta label={t("adminBroadcasts.detail.finished")} value={job.finished_at ? formatDateTime(job.finished_at) : "—"} />
          </dl>

          <section>
            <h3 className="mb-2 text-xs font-semibold text-muted">{t("adminBroadcasts.detail.errors")}</h3>
            {job.errors.length === 0 ? (
              <p className="text-sm text-muted">{t("adminBroadcasts.detail.noErrors")}</p>
            ) : (
              <ul className="divide-y divide-border rounded-xl border border-border">
                <li className="flex items-center gap-3 bg-surfaceAlt px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  <span className="shrink-0">{t("adminBroadcasts.detail.errorUser")}</span>
                  <span className="min-w-0 flex-1">{t("adminBroadcasts.detail.errorReason")}</span>
                </li>
                {job.errors.map((row) => (
                  <li key={`${row.user_id}-${row.sent_at ?? 0}`} className="flex items-start gap-3 px-3 py-2">
                    <span className="shrink-0 text-xs font-medium text-text">{row.user_id}</span>
                    <span className="min-w-0 flex-1 break-words text-xs text-muted">
                      {row.error || row.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </BottomSheet>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surfaceAlt px-3 py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium text-text">{value}</dd>
    </div>
  );
}
