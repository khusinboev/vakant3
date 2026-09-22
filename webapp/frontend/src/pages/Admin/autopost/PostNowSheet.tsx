import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { BotJobStatus, PostNowBody, PostNowResult } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import useToast from "../../../hooks/useToast";
import { useConfirmedMutation } from "../hooks/useConfirmedMutation";
import { haptic } from "../hooks/useMainButton";
import Button from "../ui/Button";
import { StatusChip } from "../ui/Chip";
import KeyValue from "../ui/KeyValue";
import { Sheet } from "../ui/Sheet";
import { AUTO_POST_HISTORY_KEY } from "./historyKey";
import { postAutoPostNowWithToken } from "./postNowApi";
import { useJobPoll } from "./useJobPoll";

const JOB_LABEL: Record<BotJobStatus, TranslationKey> = {
  queued: "adminAutopost.postNow.jobStatus.queued",
  running: "adminAutopost.postNow.jobStatus.running",
  done: "adminAutopost.postNow.jobStatus.done",
  failed: "adminAutopost.postNow.jobStatus.failed",
};

const INPUT_CLS =
  "h-9 w-full rounded-xl border border-border bg-surface px-2.5 text-[13px] text-text " +
  "placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary " +
  "disabled:opacity-60";

/**
 * The sheet's body is only mounted while the sheet is open (`Sheet` renders
 * `null` when closed), so every `useState` here resets on its own the next
 * time it's opened — no manual reset needed.
 */
function PostNowSheetBody() {
  const t = useT();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [uid, setUid] = useState("");
  const [jobId, setJobId] = useState<number | null>(null);
  const notifiedRef = useRef<number | null>(null);

  const postNow = useConfirmedMutation<PostNowBody, PostNowResult>({
    action: "autopost.post_now",
    paramKeys: [],
    titleKey: "adminAutopost.postNow.confirmTitle",
    descriptionKey: "adminAutopost.postNow.confirmDescription",
    confirmLabelKey: "adminAutopost.postNow.confirmButton",
    mutationFn: (body, token) => postAutoPostNowWithToken(body, token),
    onSuccess: (result) => setJobId(result.job_id),
  });

  const job = useJobPoll(jobId);

  useEffect(() => {
    if (!job.data || job.data.id !== jobId) return;
    if (job.data.status !== "done" && job.data.status !== "failed") return;
    if (notifiedRef.current === job.data.id) return;
    notifiedRef.current = job.data.id;
    if (job.data.status === "done") {
      haptic("success");
      toast.success(t("adminAutopost.postNow.jobDone"));
      void queryClient.invalidateQueries({ queryKey: AUTO_POST_HISTORY_KEY });
    } else {
      haptic("error");
      toast.error(job.data.error || t("adminAutopost.postNow.jobFailedGeneric"));
    }
  }, [job.data, jobId, queryClient, t, toast]);

  const trimmedUid = uid.trim();
  const submit = () => {
    const descriptionVars = { uid: trimmedUid || t("adminAutopost.postNow.nextInQueue") };
    void postNow.run({}, trimmedUid ? { uid: trimmedUid } : {}, descriptionVars);
  };

  const result = job.data?.result as { message_id?: number; uid?: string } | null | undefined;
  const showResult = jobId !== null && Boolean(job.data);
  const status = job.data?.status;

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-muted">{t("adminAutopost.postNow.description")}</p>

      <label className="block">
        <span className="mb-1 block text-[11px] font-semibold text-muted">
          {t("adminAutopost.postNow.uidLabel")}
        </span>
        <input
          type="text"
          value={uid}
          onChange={(event) => setUid(event.target.value)}
          placeholder={t("adminAutopost.postNow.uidPlaceholder")}
          disabled={jobId !== null}
          className={INPUT_CLS}
          aria-label={t("adminAutopost.postNow.uidLabel")}
        />
      </label>

      {!showResult && (
        <Button size="md" full variant="primary" loading={postNow.isPending} onClick={submit}>
          {t("adminAutopost.postNow.button")}
        </Button>
      )}

      {showResult && status && (
        <KeyValue
          rows={[
            {
              labelKey: "adminAutopost.postNow.jobStatusLabel",
              value: (
                <span className="inline-flex items-center gap-1.5">
                  <StatusChip status={status} labelKey={JOB_LABEL[status]} />
                  <span className="text-[11px] text-muted">#{job.data!.id}</span>
                </span>
              ),
            },
            {
              labelKey: "adminAutopost.postNow.resultUid",
              value: result?.uid ?? "—",
              hidden: !result?.uid,
            },
            {
              labelKey: "adminAutopost.postNow.resultMessageId",
              value: result?.message_id ?? "—",
              hidden: typeof result?.message_id !== "number",
            },
            {
              labelKey: "adminAutopost.postNow.resultError",
              value: job.data!.error || t("adminAutopost.postNow.jobFailedGeneric"),
              tone: "danger",
              hidden: status !== "failed",
            },
          ]}
        />
      )}
    </div>
  );
}

/** "Post now" — optional uid, a confirmation, then polls the resulting bot job to completion. */
export default function PostNowSheet({ name }: { name: string }) {
  return (
    <Sheet name={name} titleKey="adminAutopost.postNow.title">
      <PostNowSheetBody />
    </Sheet>
  );
}
