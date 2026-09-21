import { useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, BadgeCheck, Eraser, MessageSquare, Wallet } from "lucide-react";

import { adminKeys, banUser, messageUser, setUserPro } from "../../../api/admin";
import type { AdminUserListItem } from "../../../api/adminTypes";
import Field, { INPUT_CLS } from "../../../components/ui/Field";
import useToast from "../../../hooks/useToast";
import type { TranslationKey, TranslationVars } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import ConfirmDialog from "../components/ConfirmDialog";
import RoleGate from "../components/RoleGate";
import useConfirmedMutation from "../hooks/useConfirmedMutation";
import { postResetUser, postUserBalance } from "./api";

const MESSAGE_MAX = 4096;

type Panel = "pro" | "balance" | "ban" | "message" | "reset" | null;

type PendingConfirm = {
  titleKey: TranslationKey;
  descriptionKey?: TranslationKey;
  descriptionVars?: TranslationVars;
  danger?: boolean;
  run: () => void;
};

export type UserActionsProps = {
  user: AdminUserListItem;
};

/**
 * Every moderator/admin action on one user, gated by role and folded into
 * inline panels so nothing nests a sheet inside a sheet on mobile.
 *
 * Only `users.balance` and `wallet.reset_user` are token-confirmed on the
 * backend (CONTRACT_P12 / CONTRACT_P0), so those two go through
 * `useConfirmedMutation`; Pro and ban still ask first, with a plain
 * `ConfirmDialog`, because they are not reversible by accident.
 */
export default function UserActions({ user }: UserActionsProps) {
  const t = useT();
  const toast = useToast();
  const { formatMoney } = useLocale();
  const queryClient = useQueryClient();

  const [panel, setPanel] = useState<Panel>(null);
  const [confirm, setConfirm] = useState<PendingConfirm | null>(null);

  const [proUnlimited, setProUnlimited] = useState(false);
  const [proDays, setProDays] = useState("30");
  const [proNote, setProNote] = useState("");
  const [amount, setAmount] = useState("");
  const [balanceNote, setBalanceNote] = useState("");
  const [banReason, setBanReason] = useState("");
  const [messageText, setMessageText] = useState("");

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    void queryClient.invalidateQueries({ queryKey: adminKeys.userDetail(user.user_id) });
  };

  const closePanel = () => {
    setPanel(null);
    setConfirm(null);
  };

  const proMutation = useMutation({
    mutationFn: (body: { enabled: boolean; days: number | null; note?: string }) =>
      setUserPro(user.user_id, body),
    onSuccess: () => {
      toast.success(t("adminUsers.pro.success"));
      setProNote("");
      invalidate();
      closePanel();
    },
    onError: (error) => toast.apiError(error),
  });

  const banMutation = useMutation({
    mutationFn: (body: { banned: boolean; reason?: string }) => banUser(user.user_id, body),
    onSuccess: (_result, body) => {
      toast.success(t(body.banned ? "adminUsers.ban.success" : "adminUsers.unban.success"));
      setBanReason("");
      invalidate();
      closePanel();
    },
    onError: (error) => toast.apiError(error),
  });

  const messageMutation = useMutation({
    mutationFn: (text: string) => messageUser(user.user_id, { text }),
    onSuccess: () => {
      toast.success(t("adminUsers.message.success"));
      setMessageText("");
      closePanel();
    },
    onError: (error) => toast.apiError(error),
  });

  const balance = useConfirmedMutation<{ amount: number; note?: string }, unknown>({
    action: "users.balance",
    paramKeys: ["user_id", "amount"],
    titleKey: "adminUsers.balance.confirmTitle",
    descriptionKey: "adminUsers.balance.confirmDesc",
    successKey: "adminUsers.balance.success",
    invalidate: [["admin", "users"], adminKeys.userDetail(user.user_id)],
    mutationFn: (body, token) => postUserBalance(user.user_id, body, token),
    onSuccess: () => {
      setAmount("");
      setBalanceNote("");
      closePanel();
    },
  });

  const reset = useConfirmedMutation<{ note?: string }, unknown>({
    action: "wallet.reset_user",
    paramKeys: ["user_id"],
    danger: true,
    titleKey: "adminUsers.reset.confirmTitle",
    descriptionKey: "adminUsers.reset.confirmDesc",
    successKey: "adminUsers.reset.success",
    invalidate: [["admin", "users"], adminKeys.userDetail(user.user_id)],
    mutationFn: (body, token) => postResetUser(user.user_id, body.note, token),
    onSuccess: closePanel,
  });

  // ── submit handlers ──────────────────────────────────────────────────────

  function submitPro(enabled: boolean) {
    let days: number | null = null;
    if (enabled && !proUnlimited) {
      const parsed = Number(proDays.trim());
      if (!Number.isSafeInteger(parsed) || parsed <= 0) {
        toast.error(t("adminUsers.pro.invalidDays"));
        return;
      }
      days = parsed;
    }
    const note = proNote.trim() || undefined;
    setConfirm({
      titleKey: "adminUsers.pro.confirmTitle",
      descriptionKey: enabled ? "adminUsers.pro.confirmGrant" : "adminUsers.pro.confirmRevoke",
      descriptionVars: {
        id: user.user_id,
        term: days === null ? t("adminUsers.badge.unlimited") : t("adminUsers.pro.term", { days }),
      },
      danger: !enabled,
      run: () => proMutation.mutate({ enabled, days, note }),
    });
  }

  function submitBan(banned: boolean) {
    const reason = banReason.trim() || undefined;
    setConfirm({
      titleKey: banned ? "adminUsers.ban.confirmTitle" : "adminUsers.unban.confirmTitle",
      descriptionKey: banned ? "adminUsers.ban.confirmDesc" : "adminUsers.unban.confirmDesc",
      descriptionVars: { id: user.user_id },
      danger: banned,
      run: () => banMutation.mutate({ banned, reason }),
    });
  }

  function submitBalance() {
    const parsed = Number(amount.trim());
    if (!Number.isSafeInteger(parsed) || parsed === 0) {
      toast.error(t("adminUsers.balance.invalid"));
      return;
    }
    void balance.run(
      { user_id: user.user_id, amount: parsed },
      { amount: parsed, note: balanceNote.trim() || undefined },
      { id: user.user_id, amount: formatMoney(parsed) },
    );
  }

  function submitMessage() {
    const text = messageText.trim();
    if (!text) {
      toast.error(t("adminUsers.message.empty"));
      return;
    }
    messageMutation.mutate(text.slice(0, MESSAGE_MAX));
  }

  function submitReset() {
    void reset.run({ user_id: user.user_id }, { note: undefined }, { id: user.user_id });
  }

  // ── render ───────────────────────────────────────────────────────────────

  const toggle = (next: Exclude<Panel, null>) => setPanel((current) => (current === next ? null : next));

  const actionButton = (
    id: Exclude<Panel, null>,
    labelKey: TranslationKey,
    Icon: typeof Wallet,
    danger = false,
  ) => (
    <button
      type="button"
      onClick={() => toggle(id)}
      aria-expanded={panel === id}
      aria-controls={`user-action-${id}`}
      className={`tap-target inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition-colors ${
        panel === id
          ? "border-primary bg-primary/10 text-primary"
          : danger
            ? "border-border bg-surface text-danger"
            : "border-border bg-surface text-text"
      }`}
    >
      <Icon size={13} aria-hidden="true" />
      {t(labelKey)}
    </button>
  );

  const panelBox = (id: Exclude<Panel, null>, children: ReactNode) =>
    panel === id ? (
      <div id={`user-action-${id}`} className="space-y-3 rounded-xl border border-border bg-surfaceAlt p-3">
        {children}
      </div>
    ) : null;

  const submitCls =
    "tap-target w-full rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primaryFg disabled:opacity-50";
  const dangerCls =
    "tap-target w-full rounded-xl bg-danger px-3 py-2 text-sm font-semibold text-white disabled:opacity-50 dark:text-bg";

  return (
    <section aria-label={t("adminUsers.action.title")} className="space-y-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
        {t("adminUsers.action.title")}
      </h3>

      <div className="flex flex-wrap gap-2">
        <RoleGate min="admin" mode="disable">
          {actionButton("pro", "adminUsers.action.pro", BadgeCheck)}
        </RoleGate>
        <RoleGate min="admin" mode="disable">
          {actionButton("balance", "adminUsers.action.balance", Wallet)}
        </RoleGate>
        <RoleGate min="moderator" mode="disable">
          {actionButton(
            "ban",
            user.banned ? "adminUsers.action.unban" : "adminUsers.action.ban",
            Ban,
            !user.banned,
          )}
        </RoleGate>
        <RoleGate min="moderator" mode="disable">
          {actionButton("message", "adminUsers.action.message", MessageSquare)}
        </RoleGate>
        <RoleGate min="admin" mode="disable">
          {actionButton("reset", "adminUsers.action.reset", Eraser, true)}
        </RoleGate>
      </div>

      {panelBox(
        "pro",
        <>
          <label className="flex items-center gap-2 text-xs font-semibold text-text">
            <input
              type="checkbox"
              checked={proUnlimited}
              onChange={(event) => setProUnlimited(event.target.checked)}
              className="h-4 w-4 rounded border-border accent-primary"
            />
            {t("adminUsers.pro.unlimited")}
          </label>
          {!proUnlimited && (
            <Field label={t("adminUsers.pro.days")}>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                className={INPUT_CLS}
                value={proDays}
                onChange={(event) => setProDays(event.target.value)}
              />
            </Field>
          )}
          <Field label={t("adminUsers.pro.note")}>
            <input
              type="text"
              className={INPUT_CLS}
              value={proNote}
              onChange={(event) => setProNote(event.target.value)}
            />
          </Field>
          <div className="flex gap-2">
            <button
              type="button"
              className={submitCls}
              disabled={proMutation.isPending}
              onClick={() => submitPro(true)}
            >
              {t("adminUsers.pro.grant")}
            </button>
            <button
              type="button"
              className={dangerCls}
              disabled={proMutation.isPending || !user.is_pro}
              onClick={() => submitPro(false)}
            >
              {t("adminUsers.pro.revoke")}
            </button>
          </div>
        </>,
      )}

      {panelBox(
        "balance",
        <>
          <Field label={t("adminUsers.balance.amount")} hint={t("adminUsers.balance.hint")}>
            <input
              type="number"
              inputMode="numeric"
              className={INPUT_CLS}
              placeholder="10000"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </Field>
          <Field label={t("adminUsers.balance.note")}>
            <input
              type="text"
              className={INPUT_CLS}
              value={balanceNote}
              onChange={(event) => setBalanceNote(event.target.value)}
            />
          </Field>
          <button
            type="button"
            className={submitCls}
            disabled={balance.isPending || !amount.trim()}
            onClick={submitBalance}
          >
            {t("adminUsers.action.submit")}
          </button>
        </>,
      )}

      {panelBox(
        "ban",
        <>
          {!user.banned && (
            <Field label={t("adminUsers.ban.reason")}>
              <input
                type="text"
                className={INPUT_CLS}
                value={banReason}
                onChange={(event) => setBanReason(event.target.value)}
              />
            </Field>
          )}
          <button
            type="button"
            className={user.banned ? submitCls : dangerCls}
            disabled={banMutation.isPending}
            onClick={() => submitBan(!user.banned)}
          >
            {t(user.banned ? "adminUsers.action.unban" : "adminUsers.action.ban")}
          </button>
        </>,
      )}

      {panelBox(
        "message",
        <>
          <Field label={t("adminUsers.message.text")}>
            <textarea
              rows={4}
              maxLength={MESSAGE_MAX}
              className={INPUT_CLS}
              value={messageText}
              onChange={(event) => setMessageText(event.target.value)}
            />
          </Field>
          <p className="text-right text-[11px] text-muted" aria-live="polite">
            {t("adminUsers.message.counter", { count: messageText.length })}
          </p>
          <button
            type="button"
            className={submitCls}
            disabled={messageMutation.isPending || !messageText.trim()}
            onClick={submitMessage}
          >
            {t("adminUsers.message.send")}
          </button>
        </>,
      )}

      {panelBox(
        "reset",
        <>
          <p className="text-xs text-muted">
            {t("adminUsers.reset.confirmDesc", { id: user.user_id })}
          </p>
          <button type="button" className={dangerCls} disabled={reset.isPending} onClick={submitReset}>
            {t("adminUsers.action.reset")}
          </button>
        </>,
      )}

      <ConfirmDialog
        open={confirm !== null}
        titleKey={confirm?.titleKey ?? "adminUsers.action.title"}
        descriptionKey={confirm?.descriptionKey}
        descriptionVars={confirm?.descriptionVars}
        danger={confirm?.danger}
        loading={proMutation.isPending || banMutation.isPending}
        onConfirm={() => {
          confirm?.run();
          setConfirm(null);
        }}
        onClose={() => setConfirm(null)}
      />
    </section>
  );
}
