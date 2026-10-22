import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Eraser, Save, Send, TestTube2 } from "lucide-react";

import type {
  Broadcast,
  BroadcastButton,
  BroadcastCreateBody,
  BroadcastKind,
  UploadResult,
} from "../../../api/adminTypes";
import { createBroadcast, previewBroadcast } from "../../../api/admin";
import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import useToast from "../../../hooks/useToast";
import { useConfirmedMutation } from "../hooks/useConfirmedMutation";
import { Accordion, Chip, SegmentedControl, haptic, useAdminHeader, type AccordionItem } from "../ui";
import ButtonsEditor from "./ButtonsEditor";
import HtmlEditor from "./HtmlEditor";
import MediaUpload from "./MediaUpload";
import MessagePreview from "./MessagePreview";
import TargetPicker from "./TargetPicker";
import { queueBroadcastWithToken } from "./api";
import { COMPOSABLE_KINDS, KIND_LABEL_KEY } from "./labels";
import {
  PARAMETRIC_KINDS,
  buildSegment,
  isValidSegment,
  SEGMENT_LABEL_KEY,
  type SegmentKind,
} from "./segments";
import { checkTelegramHtml, isAllowedButtonUrl, limitForKind } from "./telegramHtml";

/**
 * `/admin/broadcasts/new` — compose → (draft) → test → queue.
 *
 * The draft is a real server row: `POST /admin/broadcasts` creates it,
 * `/preview` sends it to the acting admin only, and `/queue` materializes the
 * targets and hands the job to the bot worker. Only that last step reaches
 * users, so it is the one the header's primary action performs — behind the
 * `broadcast.queue` confirm token (spec §4 Broadcasts).
 */
export default function Composer() {
  const t = useT();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [kind, setKind] = useState<BroadcastKind>("text");
  const [text, setText] = useState("");
  const [buttons, setButtons] = useState<BroadcastButton[]>([]);
  const [media, setMedia] = useState<UploadResult | null>(null);
  const [segmentKind, setSegmentKind] = useState<SegmentKind>("all");
  const [segmentValue, setSegmentValue] = useState("");
  const [excludeBlocked, setExcludeBlocked] = useState(true);
  const [draft, setDraft] = useState<Broadcast | null>(null);
  const [estimate, setEstimate] = useState<number | null>(null);
  const [busy, setBusy] = useState<"draft" | "preview" | null>(null);

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
  const edited =
    <T,>(setter: (value: T) => void) =>
    (value: T) => {
      setDraft(null);
      setEstimate(null);
      setter(value);
    };

  const body = (): BroadcastCreateBody => ({
    kind,
    text: check.html || undefined,
    buttons: cleanButtons,
    media_path: media?.path,
    segment,
    exclude_blocked: excludeBlocked,
  });

  /**
   * The draft row the test send and the queue call both need. Creating it is
   * not destructive (nothing is sent), and `createBroadcast` mints its own
   * `broadcast.create` token — so no second dialog in front of the queue one.
   */
  const ensureDraft = async (announce: boolean): Promise<Broadcast | null> => {
    if (draft) return draft;
    if (!canSave) return null;
    setBusy("draft");
    try {
      const created = await createBroadcast(body());
      setDraft(created);
      void queryClient.invalidateQueries({ queryKey: ["admin", "broadcasts"] });
      if (announce) {
        haptic("success");
        toast.success(t("adminBroadcasts.ok.draftSaved"));
      }
      return created;
    } catch (error) {
      haptic("error");
      toast.apiError(error);
      return null;
    } finally {
      setBusy(null);
    }
  };

  const sendTest = async () => {
    const row = await ensureDraft(false);
    if (!row) return;
    setBusy("preview");
    try {
      await previewBroadcast(row.id);
      haptic("success");
      toast.success(t("adminBroadcasts.ok.testSent"));
    } catch (error) {
      haptic("error");
      toast.apiError(error);
    } finally {
      setBusy(null);
    }
  };

  // `/queue` is the step that actually reaches users, so the server requires a
  // confirmation token bound to this exact broadcast id (`broadcast.queue`).
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
    mutationFn: (payload, token) => queueBroadcastWithToken(payload.broadcast_id, token),
    onSuccess: (result) => setEstimate(result.total),
  });

  const queue = async () => {
    const row = await ensureDraft(false);
    if (!row) return;
    const result = await queueMutation.run({ broadcast_id: row.id }, { broadcast_id: row.id }, {
      segment: t(SEGMENT_LABEL_KEY[segmentKind]),
    });
    if (result) {
      setDraft(null);
      navigate(`/admin/broadcasts/${row.id}`, { replace: true });
    }
  };

  const reset = () => {
    setText("");
    setButtons([]);
    setMedia(null);
    setDraft(null);
    setEstimate(null);
  };

  const pending = busy !== null || queueMutation.isPending;

  useAdminHeader({
    titleKey: "adminBroadcasts.composer.title",
    primary: {
      labelKey: "adminBroadcasts.action.queue",
      icon: Send,
      onClick: () => void queue(),
      disabled: !canSave || pending,
      loading: queueMutation.isPending,
    },
    menu: [
      {
        labelKey: "adminBroadcasts.action.sendTest",
        icon: TestTube2,
        onClick: () => void sendTest(),
        disabled: !canSave || pending,
      },
      {
        labelKey: "adminBroadcasts.action.saveDraft",
        icon: Save,
        onClick: () => void ensureDraft(true),
        disabled: !canSave || pending || draft !== null,
      },
      { labelKey: "adminBroadcasts.composer.reset", icon: Eraser, onClick: reset },
    ],
  });

  const segmentSummary = PARAMETRIC_KINDS.includes(segmentKind)
    ? `${t(SEGMENT_LABEL_KEY[segmentKind])}: ${segmentValue || "—"}`
    : t(SEGMENT_LABEL_KEY[segmentKind]);

  const sections: AccordionItem[] = [
    {
      id: "text",
      titleKey: "adminBroadcasts.section.text",
      summary: `${check.length} / ${limit}`,
      content: (
        <div className="space-y-2">
          <HtmlEditor
            value={text}
            onChange={edited(setText)}
            labelKey={
              kind === "text" ? "adminBroadcasts.composer.text" : "adminBroadcasts.composer.caption"
            }
            limit={limit}
            check={check}
          />
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            {t("adminBroadcasts.composer.preview")}
          </p>
          <MessagePreview html={check.html} buttons={cleanButtons} />
        </div>
      ),
    },
  ];

  if (kind !== "text") {
    sections.push({
      id: "media",
      titleKey: "adminBroadcasts.section.media",
      summary: media ? media.path.split("/").pop() : t("adminBroadcasts.media.none"),
      content: <MediaUpload value={media} onChange={edited(setMedia)} />,
    });
  }

  sections.push(
    {
      id: "buttons",
      titleKey: "adminBroadcasts.section.buttons",
      summary: t("adminBroadcasts.buttons.count", { count: cleanButtons.length }),
      content: <ButtonsEditor value={buttons} onChange={edited(setButtons)} />,
    },
    {
      id: "target",
      titleKey: "adminBroadcasts.section.target",
      summary: segmentSummary,
      content: (
        <TargetPicker
          kind={segmentKind}
          value={segmentValue}
          onKindChange={edited(setSegmentKind)}
          onValueChange={edited(setSegmentValue)}
          excludeBlocked={excludeBlocked}
          onExcludeBlockedChange={edited(setExcludeBlocked)}
          estimate={estimate}
        />
      ),
    },
  );

  return (
    <div className="space-y-2">
      <SegmentedControl
        full
        options={COMPOSABLE_KINDS.map((option) => ({
          value: option,
          labelKey: KIND_LABEL_KEY[option],
        }))}
        value={kind}
        onChange={(next) => {
          setDraft(null);
          setEstimate(null);
          setKind(next as BroadcastKind);
          if (next === "text") setMedia(null);
        }}
        ariaLabel={t("adminBroadcasts.composer.kind")}
      />

      <Accordion queryKey="sec" defaultOpen="text" items={sections} />

      {draft ? (
        <Chip tone="primary" label={t("adminBroadcasts.composer.draftId", { id: draft.id })} />
      ) : blockedReason ? (
        <p role="status" className="text-[11px] text-muted">
          {t(blockedReason)}
        </p>
      ) : null}
    </div>
  );
}
