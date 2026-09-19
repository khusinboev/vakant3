import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import client from "../../api/client";
import useToast from "../../hooks/useToast";
import { useT } from "../../i18n/useT";
import { isApiErrorCode } from "../../lib/parseApiError";
import {
  normalizeProfile,
  profileHasContent,
  type ResumeDoc,
  type ResumeEventPayload,
  type ResumeProfileResponse,
  type ResumeTemplateItem,
  type StepId,
} from "./types";

const AUTOSAVE_INTERVAL_MS = 15_000;
const PROFILE_POLL_MS = 30_000;

export type SyncStatus = "idle" | "saving" | "synced" | "error";

type Params = {
  userId: number | undefined;
  doc: ResumeDoc;
  /** Change signature of `doc`, used to tell a stale save from a current one. */
  fingerprint: string;
  dirtyRef: React.MutableRefObject<boolean>;
  /** Epoch ms of the local draft, compared with the server's `updated_at`. */
  localDraftAtRef: React.MutableRefObject<number>;
  currentStep: StepId;
  applyServer: (server: ResumeProfileResponse) => void;
  markSynced: (fingerprint: string, current: string) => void;
  /** A premium template was rejected by the API — open the upsell. */
  onPremiumBlocked: () => void;
};

function now(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

/** `resume_save:1730712345678:x7f2ab` — matches the API's IDEMPOTENCY_RE. */
function idempotencyKey(action: string): string {
  return `${action}:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Everything the wizard does over the network: loading the profile and the
 * template catalogue, explicit saves, the 15 s autosave, Telegram delivery,
 * analytics events, and detecting that another device saved a newer copy.
 */
export function useResumeSync({
  userId,
  doc,
  fingerprint,
  dirtyRef,
  localDraftAtRef,
  currentStep,
  applyServer,
  markSynced,
  onPremiumBlocked,
}: Params) {
  const queryClient = useQueryClient();
  const t = useT();
  const toast = useToast();

  const [syncStatus, setSyncStatus] = useState<SyncStatus>("idle");
  const [serverDraftAvailable, setServerDraftAvailable] = useState(false);
  const [conflict, setConflict] = useState(false);

  const hydratedRef = useRef(false);
  const openedTrackedRef = useRef(false);
  const readyTrackedRef = useRef(false);
  const screenStartRef = useRef(now());
  const serverUpdatedAtRef = useRef(0);
  const syncFpRef = useRef("");
  const savePendingRef = useRef(false);
  const sendPendingRef = useRef(false);
  const autoSavePendingRef = useRef(false);
  // Read inside mutation callbacks and the autosave interval, where a captured
  // value would be stale.
  const docRef = useRef(doc);
  docRef.current = doc;
  const fingerprintRef = useRef(fingerprint);
  fingerprintRef.current = fingerprint;
  const stepRef = useRef<StepId>(currentStep);
  stepRef.current = currentStep;

  /** Only try the API when there is some credential to authenticate with. */
  const authHintAvailable = useMemo(
    () =>
      Boolean(
        localStorage.getItem("session_token") ||
          window.Telegram?.WebApp?.initData ||
          window.Telegram?.WebApp?.initDataUnsafe?.user?.id,
      ),
    [],
  );

  const trackEvent = useCallback((payload: ResumeEventPayload) => {
    // Fire-and-forget: analytics must never surface an error to the user.
    void client.post("/resume/events", payload).catch(() => undefined);
  }, []);

  const profileQuery = useQuery({
    queryKey: ["resume", "profile", userId],
    queryFn: async () => {
      const { data } = await client.get<ResumeProfileResponse>("/resume/profile");
      return data;
    },
    retry: false,
    enabled: authHintAvailable,
    refetchInterval: PROFILE_POLL_MS,
  });

  const templatesQuery = useQuery({
    queryKey: ["resume", "templates"],
    queryFn: async () => {
      const { data } = await client.get<{ items: ResumeTemplateItem[] }>("/resume/templates");
      return data.items;
    },
    retry: false,
    enabled: authHintAvailable,
  });

  const walletQuery = useQuery({
    queryKey: ["wallet"],
    queryFn: async () => {
      const { data } = await client.get<{ balance: number; is_pro: boolean }>("/wallet");
      return data;
    },
    retry: false,
    enabled: authHintAvailable,
    staleTime: 60_000,
  });

  const persistProfile = useCallback(
    async (action: string): Promise<ResumeProfileResponse> => {
      const current = docRef.current;
      syncFpRef.current = fingerprintRef.current;
      const { data } = await client.put<ResumeProfileResponse>(
        "/resume/profile",
        {
          profile: current.profile,
          selected_template: current.selectedTemplate,
          accent_color: current.accentColor,
        },
        { headers: { "X-Idempotency-Key": idempotencyKey(action) } },
      );
      return data;
    },
    [],
  );

  const acceptSaved = useCallback(
    (data: ResumeProfileResponse) => {
      queryClient.setQueryData(["resume", "profile", userId], data);
      serverUpdatedAtRef.current = Number(data.updated_at || serverUpdatedAtRef.current);
      markSynced(syncFpRef.current, fingerprintRef.current);
      setConflict(false);
      setSyncStatus("synced");
    },
    [queryClient, userId, markSynced],
  );

  const handleWriteError = useCallback(
    (error: unknown) => {
      setSyncStatus("error");
      if (isApiErrorCode(error, "PREMIUM_TEMPLATE")) {
        onPremiumBlocked();
        return;
      }
      toast.apiError(error);
    },
    [onPremiumBlocked, toast],
  );

  // ── Mutations ─────────────────────────────────────────────────────────────
  const saveMutation = useMutation({
    retry: false,
    onMutate: () => {
      savePendingRef.current = true;
      setSyncStatus("saving");
    },
    mutationFn: async () => {
      const startedAt = now();
      const data = await persistProfile("resume_save");
      return { data, latencyMs: Math.max(0, Math.round(now() - startedAt)) };
    },
    onSuccess: ({ data, latencyMs }) => {
      acceptSaved(data);
      toast.success(t("resume.toast.saved"));
      trackEvent({
        event_name: "save_success",
        step: stepRef.current,
        meta_json: JSON.stringify({ latency_ms: latencyMs }),
      });
    },
    onError: (error) => {
      handleWriteError(error);
      trackEvent({ event_name: "save_error", step: stepRef.current });
    },
    onSettled: () => {
      savePendingRef.current = false;
    },
  });

  const autoSaveMutation = useMutation({
    retry: false,
    onMutate: () => {
      autoSavePendingRef.current = true;
      setSyncStatus("saving");
    },
    mutationFn: async () => {
      const startedAt = now();
      const data = await persistProfile("resume_autosave");
      return { data, latencyMs: Math.max(0, Math.round(now() - startedAt)) };
    },
    onSuccess: ({ data, latencyMs }) => {
      acceptSaved(data);
      trackEvent({
        event_name: "autosave_success",
        step: stepRef.current,
        meta_json: JSON.stringify({ latency_ms: latencyMs }),
      });
    },
    onError: (error) => {
      // An autosave failure is silent apart from the header pill, except when it
      // is the premium gate — that needs the upsell.
      setSyncStatus("error");
      if (isApiErrorCode(error, "PREMIUM_TEMPLATE")) onPremiumBlocked();
      trackEvent({ event_name: "autosave_error", step: stepRef.current });
    },
    onSettled: () => {
      autoSavePendingRef.current = false;
    },
  });

  const sendMutation = useMutation({
    retry: false,
    onMutate: () => {
      sendPendingRef.current = true;
    },
    mutationFn: async () => {
      const startedAt = now();
      await persistProfile("resume_send_persist");
      // The response carries no prose any more, only {ok, status}.
      await client.post("/resume/send-telegram", { template_id: docRef.current.selectedTemplate });
      return { latencyMs: Math.max(0, Math.round(now() - startedAt)) };
    },
    onSuccess: ({ latencyMs }) => {
      toast.success(t("resume.toast.sent"));
      void queryClient.invalidateQueries({ queryKey: ["resume", "profile", userId] });
      trackEvent({
        event_name: "send_success",
        step: "final",
        meta_json: JSON.stringify({ latency_ms: latencyMs }),
      });
    },
    onError: (error) => {
      handleWriteError(error);
      trackEvent({ event_name: "send_error", step: "final" });
    },
    onSettled: () => {
      sendPendingRef.current = false;
    },
  });

  const autoSaveRef = useRef(autoSaveMutation);
  autoSaveRef.current = autoSaveMutation;

  // ── Periodic autosave ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!authHintAvailable) return;
    const interval = setInterval(() => {
      if (
        dirtyRef.current &&
        hydratedRef.current &&
        !savePendingRef.current &&
        !sendPendingRef.current &&
        !autoSavePendingRef.current
      ) {
        autoSaveRef.current.mutate();
      }
    }, AUTOSAVE_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [authHintAvailable, dirtyRef]);

  // ── Hydration + conflict detection ────────────────────────────────────────
  useEffect(() => {
    const data = profileQuery.data;
    if (!data) return;
    const serverSeconds = Number(data.updated_at || 0);

    if (!hydratedRef.current) {
      hydratedRef.current = true;
      serverUpdatedAtRef.current = serverSeconds;
      // The form is never auto-filled from the server: if the server copy is
      // newer than the local draft we offer to load it instead.
      const hasContent = profileHasContent(normalizeProfile(data.profile));
      if (hasContent && serverSeconds * 1000 > localDraftAtRef.current) setServerDraftAvailable(true);
    } else if (serverSeconds > serverUpdatedAtRef.current) {
      // Another device (or tab) saved after us.
      if (dirtyRef.current) {
        setConflict(true);
      } else {
        applyServer(data);
        serverUpdatedAtRef.current = serverSeconds;
      }
    }

    if (!openedTrackedRef.current) {
      openedTrackedRef.current = true;
      trackEvent({ event_name: "builder_opened", step: "basic" });
    }
    if (!readyTrackedRef.current) {
      readyTrackedRef.current = true;
      trackEvent({
        event_name: "builder_ready",
        step: "basic",
        meta_json: JSON.stringify({ ttfi_ms: Math.max(0, Math.round(now() - screenStartRef.current)) }),
      });
    }
  }, [profileQuery.data, applyServer, dirtyRef, localDraftAtRef, trackEvent]);

  const loadFromServer = useCallback(() => {
    const data = profileQuery.data;
    if (!data) return;
    applyServer(data);
    serverUpdatedAtRef.current = Number(data.updated_at || 0);
    setServerDraftAvailable(false);
    setConflict(false);
    setSyncStatus("synced");
    toast.info(t("resume.serverDraft.loaded"));
  }, [profileQuery.data, applyServer, toast, t]);

  /** Keep the local edits: the next save overwrites the server copy. */
  const keepLocal = useCallback(() => {
    serverUpdatedAtRef.current = Number(profileQuery.data?.updated_at || serverUpdatedAtRef.current);
    setConflict(false);
  }, [profileQuery.data]);

  return {
    authHintAvailable,
    profileQuery,
    templatesQuery,
    isPro: walletQuery.data?.is_pro ?? false,
    hydratedRef,
    syncStatus,
    serverDraftAvailable,
    conflict,
    loadFromServer,
    keepLocal,
    save: saveMutation.mutate,
    send: sendMutation.mutate,
    saving: saveMutation.isPending,
    sending: sendMutation.isPending,
    isBusy: saveMutation.isPending || sendMutation.isPending,
    trackEvent,
  };
}

export default useResumeSync;
