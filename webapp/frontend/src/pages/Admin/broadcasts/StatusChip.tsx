import type { BroadcastStatus } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

const LABEL_KEY: Record<BroadcastStatus, TranslationKey> = {
  draft: "adminBroadcasts.status.draft",
  queued: "adminBroadcasts.status.queued",
  running: "adminBroadcasts.status.running",
  paused: "adminBroadcasts.status.paused",
  cancelled: "adminBroadcasts.status.cancelled",
  done: "adminBroadcasts.status.done",
  failed: "adminBroadcasts.status.failed",
};

const TONE: Record<BroadcastStatus, string> = {
  draft: "bg-surfaceAlt text-muted border-border",
  queued: "bg-primary/10 text-primary border-primary/30",
  running: "bg-primary/15 text-primary border-primary/40",
  paused: "bg-warning/10 text-warning border-warning/30",
  cancelled: "bg-surfaceAlt text-muted border-border",
  done: "bg-success/10 text-success border-success/30",
  failed: "bg-danger/10 text-danger border-danger/30",
};

/** Status of a broadcast as a coloured chip; `running` gets a pulsing dot. */
export default function StatusChip({ status }: { status: BroadcastStatus }) {
  const t = useT();
  const key = LABEL_KEY[status] ?? LABEL_KEY.draft;
  const tone = TONE[status] ?? TONE.draft;

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}
    >
      {status === "running" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />
      )}
      {t(key)}
    </span>
  );
}
