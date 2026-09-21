import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Send, X } from "lucide-react";

import Field, { INPUT_CLS } from "../../../components/ui/Field";
import useToast from "../../../hooks/useToast";
import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import GroupCard from "../components/GroupCard";
import { useConfirmedMutation } from "../hooks/useConfirmedMutation";
import type { BotJobStatus, PostNowBody, PostNowResult } from "../../../api/adminTypes";
import { postAutoPostNowWithToken } from "./postNowApi";
import { useJobPoll } from "./useJobPoll";
import StatusBadge, { type BadgeTone } from "./StatusBadge";
import { AUTO_POST_HISTORY_KEY } from "./historyKey";

const JOB_TONE: Record<BotJobStatus, BadgeTone> = {
  queued: "muted",
  running: "warning",
  done: "success",
  failed: "danger",
};

const JOB_LABEL: Record<BotJobStatus, TranslationKey> = {
  queued: "adminAutopost.postNow.jobStatus.queued",
  running: "adminAutopost.postNow.jobStatus.running",
  done: "adminAutopost.postNow.jobStatus.done",
  failed: "adminAutopost.postNow.jobStatus.failed",
};

/** "Post now" — optional uid, a confirmation, then polls the resulting bot job to completion. */
export default function PostNowCard() {
  const t = useT();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [uid, setUid] = useState("");
  const [jobId, setJobId] = useState<number | null>(null);

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
  const notifiedRef = useRef<number | null>(null);

  useEffect(() => {
    if (!job.data || job.data.id !== jobId) return;
    if (job.data.status !== "done" && job.data.status !== "failed") return;
    if (notifiedRef.current === job.data.id) return;
    notifiedRef.current = job.data.id;
    if (job.data.status === "done") {
      toast.success(t("adminAutopost.postNow.jobDone"));
      void queryClient.invalidateQueries({ queryKey: AUTO_POST_HISTORY_KEY });
    } else {
      toast.error(job.data.error || t("adminAutopost.postNow.jobFailedGeneric"));
    }
  }, [job.data, jobId, queryClient, t, toast]);

  const trimmedUid = uid.trim();

  const submit = () => {
    const descriptionVars = { uid: trimmedUid || t("adminAutopost.postNow.nextInQueue") };
    void postNow.run({}, trimmedUid ? { uid: trimmedUid } : {}, descriptionVars);
  };

  const result = job.data?.result as { message_id?: number; uid?: string } | null | undefined;
  const showResult = jobId !== null && job.data;

  return (
    <GroupCard icon={Send} title={t("adminAutopost.postNow.title")}>
      <div className="space-y-3 py-3">
        <p className="text-xs text-muted">{t("adminAutopost.postNow.description")}</p>

        <Field label={t("adminAutopost.postNow.uidLabel")} hint={t("adminAutopost.postNow.uidHint")}>
          <input
            type="text"
            value={uid}
            onChange={(event) => setUid(event.target.value)}
            placeholder={t("adminAutopost.postNow.uidPlaceholder")}
            className={INPUT_CLS}
            aria-label={t("adminAutopost.postNow.uidLabel")}
          />
        </Field>

        <button
          type="button"
          onClick={submit}
          disabled={postNow.isPending}
          className="tap-target inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primaryFg disabled:opacity-60 sm:w-auto"
        >
          <Send size={14} aria-hidden="true" />
          {postNow.isPending ? t("adminAutopost.postNow.sending") : t("adminAutopost.postNow.button")}
        </button>

        {showResult && (
          <div className="relative rounded-xl border border-border bg-surfaceAlt p-3">
            <button
              type="button"
              onClick={() => {
                setJobId(null);
                notifiedRef.current = null;
              }}
              aria-label={t("adminAutopost.postNow.dismiss")}
              className="tap-target absolute right-2 top-2 rounded-full p-1 text-muted hover:text-text"
            >
              <X size={14} aria-hidden="true" />
            </button>
            <div className="flex items-center gap-2 pr-6">
              <StatusBadge tone={JOB_TONE[job.data!.status] ?? "muted"} labelKey={JOB_LABEL[job.data!.status]} />
              <span className="text-xs text-muted">#{job.data!.id}</span>
            </div>
            <dl className="mt-2 space-y-1 text-xs text-text">
              {result?.uid && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted">{t("adminAutopost.postNow.resultUid")}</dt>
                  <dd className="truncate font-medium">{result.uid}</dd>
                </div>
              )}
              {typeof result?.message_id === "number" && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted">{t("adminAutopost.postNow.resultMessageId")}</dt>
                  <dd className="font-medium">{result.message_id}</dd>
                </div>
              )}
              {job.data!.status === "failed" && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted">{t("adminAutopost.postNow.resultError")}</dt>
                  <dd className="truncate font-medium text-danger">
                    {job.data!.error || t("adminAutopost.postNow.jobFailedGeneric")}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        )}
      </div>
    </GroupCard>
  );
}
