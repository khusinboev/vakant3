import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import client from "../api/client";
import { useT } from "../i18n/useT";
import { botDeepLink, openTelegramLink } from "../lib/constants";
import { shareRefLink } from "../lib/share";
import type { GateBlockReason, GateState } from "../lib/entryGate";
import { gateBlockReason } from "../lib/entryGate";
import { useAuthStore } from "../store/auth";

function Card({ title, body, children }: { title: string; body: string; children?: React.ReactNode }) {
  return (
    <div className="mx-auto mt-6 max-w-xl px-4">
      <div className="card p-5 text-center">
        <p className="text-base font-semibold text-text">{title}</p>
        <p className="mt-2 text-sm text-muted">{body}</p>
        {children}
      </div>
    </div>
  );
}

export default function EntryLockScreen({
  reason,
  gate,
}: {
  reason: GateBlockReason;
  gate: GateState;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const userId = useAuthStore((s) => s.user?.user_id);
  const [checking, setChecking] = useState(false);
  const [failed, setFailed] = useState(false);

  const recheck = async () => {
    setChecking(true);
    setFailed(false);
    try {
      const { data } = await client.post<GateState>("/auth/gate/recheck");
      queryClient.setQueryData(["auth", "gate"], data);
      if (gateBlockReason(data) === null) {
        // Everything cached while locked was fetched behind a 403.
        void queryClient.invalidateQueries();
      } else {
        setFailed(true);
      }
    } catch {
      setFailed(true);
    } finally {
      setChecking(false);
    }
  };

  if (reason === "banned") {
    return <Card title={t("gate.bannedTitle")} body={t("gate.bannedBody")} />;
  }

  if (reason === "bot_start") {
    return (
      <Card title={t("gate.botStartTitle")} body={t("gate.botStartBody")}>
        <button
          type="button"
          onClick={() => openTelegramLink(botDeepLink("app"))}
          className="tap-target mt-4 inline-block rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primaryFg"
        >
          {t("gate.botStartAction")}
        </button>
      </Card>
    );
  }

  if (reason === "subscribe") {
    return (
      <Card title={t("gate.subscribeTitle")} body={t("gate.subscribeBody")}>
        <div className="mt-4 space-y-2">
          {gate.channels.map((channel, index) => (
            <button
              key={channel.id}
              type="button"
              disabled={!channel.invite_link}
              onClick={() => channel.invite_link && openTelegramLink(channel.invite_link)}
              className="tap-target block w-full rounded-2xl border border-border bg-surfaceAlt px-4 py-2 text-sm font-semibold text-text disabled:opacity-50"
            >
              {index + 1}. {channel.title || channel.username || t("gate.channelFallback")}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={recheck}
          disabled={checking}
          className="tap-target mt-4 inline-block rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primaryFg disabled:opacity-60"
        >
          {checking ? t("gate.checking") : t("gate.checkAgain")}
        </button>
        {failed ? <p className="mt-3 text-sm text-warning">{t("gate.stillLocked")}</p> : null}
      </Card>
    );
  }

  return (
    <Card title={t("app.referralLockTitle")} body={t("app.referralLockBody")}>
      <p className="mt-3 text-sm font-semibold text-warning">
        {t("app.referralLockStatus", {
          current: gate.referral.count,
          required: gate.referral.required,
        })}
      </p>
      <button
        type="button"
        onClick={() =>
          shareRefLink(botDeepLink(`ref_${userId ?? ""}`), t("referral.shareText"))
        }
        className="tap-target mt-4 inline-block rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primaryFg"
      >
        {t("app.referralLockShare")}
      </button>
      <button
        type="button"
        onClick={recheck}
        disabled={checking}
        className="tap-target mt-2 inline-block rounded-2xl border border-border px-4 py-2 text-sm font-semibold text-text disabled:opacity-60"
      >
        {checking ? t("gate.checking") : t("gate.checkAgain")}
      </button>
    </Card>
  );
}
