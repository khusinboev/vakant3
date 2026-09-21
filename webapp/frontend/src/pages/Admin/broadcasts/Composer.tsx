import { useMemo, useState } from "react";
import { Eraser, Loader2, Send, Save, TestTube2 } from "lucide-react";

import type {
  Broadcast,
  BroadcastButton,
  BroadcastCreateBody,
  BroadcastKind,
  UploadResult,
} from "../../../api/adminTypes";
import { previewBroadcast } from "../../../api/admin";
import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import useToast from "../../../hooks/useToast";
import { INPUT_CLS } from "../../../components/ui/Field";
import { useConfirmedMutation } from "../hooks/useConfirmedMutation";
import ButtonsEditor from "./ButtonsEditor";
import HtmlEditor from "./HtmlEditor";
import MediaUpload from "./MediaUpload";
import TargetPicker from "./TargetPicker";
import { createBroadcastWithToken, queueBroadcastWithToken } from "./api";
import { COMPOSABLE_KINDS, KIND_LABEL_KEY } from "./labels";
import { buildSegment, isValidSegment, SEGMENT_LABEL_KEY, type SegmentKind } from "./segments";
import {
  checkTelegramHtml,
  isAllowedButtonUrl,
  limitForKind,
} from "./telegramHtml";

export type ComposerProps = {
  /** Called once a broadcast is queued, so the list next to it can refresh. */
  onQueued: () => void;
};

/**
 * Compose → save draft → test → queue.
 *
 * The draft is a real server row: `POST /admin/broadcasts` creates it (behind
 * the confirm dialog, action `broadcast.create` bound to `kind` + `segment`),
 * `/preview` sends it to the acting admin only, and `/queue` materializes the
 * targets and hands the job to the bot worker. Nothing reaches a user before
 * that last step, which is why only the *create* is confirmed here.
 */
export default function Composer({ onQueued }: ComposerProps) {
  const t = useT();
  const toast = useToast();

  const [kind, setKind] = useState<BroadcastKind>("text");
  const [text, setText] = useState("");
  const [buttons, setButtons] = useState<BroadcastButton[]>([]);
  const [media, setMedia] = useState<UploadResult | null>(null);
  const [segmentKind, setSegmentKind] = useState<SegmentKind>("all");
  const [segmentValue, setSegmentValue] = useState("");
  const [excludeBlocked, setExcludeBlocked] = useState(true);
  const [draft, setDraft] = useState<Broadcast | null>(null);
  const [estimate, setEstimate] = useState<number | null>(null);
  const [busy, setBusy] = useState<"preview" | null>(null);

  const limit = limitForKind(kind);
  const check = useMemo(() => checkTelegramHtml(text), [text]);
  const segment = buildSegment(segmentKind, segmentValue);

  const cleanButtons = buttons.filter((row) => row.text.trim() || row.url.trim());
  const buttonsValid = cleanButtons.every(
    (row) => row.text.trim().length > 0 && isAllowedButtonUrl(row.url),
  );

  const canSave =
    check.reason === null &&
    check.length <= limit &&
    buttonsValid &&
    isValidSegment(segment) &&
    (kind === "text" ? check.length > 0 : media !== null);

  /** What still stands between the draft and the server, for the hint line. */
  const blockedReason: TranslationKey | null =
    kind !== "text" && !media
      ? "adminBroadcasts.error.mediaRequired"
      : kind === "text" && check.length === 0
        ? "adminBroadcasts.error.textRequired"
        : check.length > limit
          ? "adminBroadcasts.error.tooLong"
          : null;

  // Any edit invalidates the saved draft: the row on the server no longer
  // matches what is on screen, so it must be re-created before sending.
  const edited = <T,>(setter: (value: T) => void) => (value: T) => {
    setDraft(null);
    setEstimate(null);
    setter(value);
  };

  const create = useConfirmedMutation<BroadcastCreateBody, Broadcast>({
    action: "broadcast.create",
    paramKeys: ["kind", "segment"],
    titleKey: "adminBroadcasts.confirm.createTitle",
    descriptionKey: "adminBroadcasts.confirm.createDesc",
    confirmLabelKey: "adminBroadcasts.action.saveDraft",
    successKey: "adminBroadcasts.ok.draftSaved",
    invalidate: [["admin", "broadcasts"]],
    mutationFn: (body, token) => createBroadcastWithToken(body, token),
    onSuccess: (created) => setDraft(created),
  });

  const saveDraft = () =>
    create.run(
      { kind, segment },
      {
        kind,
        text: check.html || undefined,
        buttons: cleanButtons,
        media_path: media?.path,
        segment,
        exclude_blocked: excludeBlocked,
      },
      { kind: t(KIND_LABEL_KEY[kind]), segment: t(SEGMENT_LABEL_KEY[segmentKind]) },
    );

  const sendTest = async () => {
    if (!draft) return;
    setBusy("preview");
    try {
      await previewBroadcast(draft.id);
      toast.success(t("adminBroadcasts.ok.testSent"));
    } catch (error) {
      toast.apiError(error);
    } finally {
      setBusy(null);
    }
  };

  // `/queue` is the step that actually reaches users, so the server requires a
  // confirmation token bound to this exact broadcast id (`broadcast.queue`) —
  // the dialog is no longer just a client-side courtesy.
  const queueMutation = useConfirmedMutation<
    { broadcast_id: number },
    { id: number; status: string; total: number }
  >({
    action: "broadcast.queue",
    paramKeys: ["broadcast_id"],
    titleKey: "adminBroadcasts.confirm.queueTitle",
    descriptionKey: "adminBroadcasts.confirm.queueDesc",
    confirmLabelKey: "adminBroadcasts.action.queue",
    successKey: "adminBroadcasts.ok.queued",
    danger: true,
    invalidate: [["admin", "broadcasts"]],
    mutationFn: (body, token) => queueBroadcastWithToken(body.broadcast_id, token),
    onSuccess: (result) => {
      setEstimate(result.total);
      setDraft(null);
      onQueued();
    },
  });

  const queue = () => {
    if (!draft) return;
    void queueMutation.run({ broadcast_id: draft.id }, { broadcast_id: draft.id }, {
      segment: t(SEGMENT_LABEL_KEY[segmentKind]),
    });
  };

  const reset = () => {
    setText("");
    setButtons([]);
    setMedia(null);
    setDraft(null);
    setEstimate(null);
  };

  return (
    <section className="space-y-4" aria-label={t("adminBroadcasts.composer.title")}>
      <div className="rounded-2xl border border-border bg-surface p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-text">{t("adminBroadcasts.composer.title")}</h2>
          {draft && (
            <span className="rounded-full bg-surfaceAlt px-2 py-0.5 text-xs text-muted">
              {t("adminBroadcasts.composer.draftId", { id: draft.id })}
            </span>
          )}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="broadcast-kind" className="block text-xs font-semibold text-muted">
            {t("adminBroadcasts.composer.kind")}
          </label>
          <select
            id="broadcast-kind"
            value={kind}
            onChange={(event) => {
              const next = event.target.value as BroadcastKind;
              setDraft(null);
              setEstimate(null);
              setKind(next);
              if (next === "text") setMedia(null);
            }}
            className={INPUT_CLS}
          >
            {COMPOSABLE_KINDS.map((option) => (
              <option key={option} value={option}>
                {t(KIND_LABEL_KEY[option])}
              </option>
            ))}
          </select>
        </div>

        {kind !== "text" && <MediaUpload value={media} onChange={edited(setMedia)} />}

        <HtmlEditor
          value={text}
          onChange={edited(setText)}
          labelKey={kind === "text" ? "adminBroadcasts.composer.text" : "adminBroadcasts.composer.caption"}
          limit={limit}
          check={check}
          previewFooter={
            cleanButtons.length > 0 ? (
              <div className="mt-3 space-y-1.5">
                {cleanButtons.map((row, index) => (
                  <div
                    key={index}
                    className="truncate rounded-lg bg-surface px-3 py-2 text-center text-sm font-medium text-primary"
                  >
                    {row.text || row.url}
                  </div>
                ))}
              </div>
            ) : null
          }
        />

        <ButtonsEditor value={buttons} onChange={edited(setButtons)} />
      </div>

      <div className="rounded-2xl border border-border bg-surface p-4">
        <TargetPicker
          kind={segmentKind}
          value={segmentValue}
          onKindChange={edited(setSegmentKind)}
          onValueChange={edited(setSegmentValue)}
          excludeBlocked={excludeBlocked}
          onExcludeBlockedChange={edited(setExcludeBlocked)}
          estimate={estimate}
        />
      </div>

      {blockedReason && (
        <p role="status" className="text-xs text-muted">
          {t(blockedReason)}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void saveDraft()}
          disabled={!canSave || create.isPending || busy !== null || queueMutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-2 text-sm font-semibold text-primaryFg disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          {create.isPending ? <Spinner /> : <Save size={15} aria-hidden="true" />}
          {t("adminBroadcasts.action.saveDraft")}
        </button>

        <button
          type="button"
          onClick={() => void sendTest()}
          disabled={!draft || busy !== null || queueMutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-xl border border-border px-3.5 py-2 text-sm font-medium text-text hover:bg-surfaceAlt disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          {busy === "preview" ? <Spinner /> : <TestTube2 size={15} aria-hidden="true" />}
          {t("adminBroadcasts.action.sendTest")}
        </button>

        <button
          type="button"
          onClick={queue}
          disabled={!draft || busy !== null || queueMutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-xl bg-success px-3.5 py-2 text-sm font-semibold text-primaryFg disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          {queueMutation.isPending ? <Spinner /> : <Send size={15} aria-hidden="true" />}
          {t("adminBroadcasts.action.queue")}
        </button>

        <button
          type="button"
          onClick={reset}
          className="ml-auto inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm text-muted hover:bg-surfaceAlt hover:text-text focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          <Eraser size={15} aria-hidden="true" /> {t("adminBroadcasts.composer.reset")}
        </button>
      </div>
    </section>
  );
}

function Spinner() {
  return <Loader2 size={15} className="animate-spin" aria-hidden="true" />;
}
