import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { banUser, messageUser, setUserPro } from "../../../api/admin";
import type { AdminUserListItem } from "../../../api/adminTypes";
import useToast from "../../../hooks/useToast";
import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { closeConfirm, requestConfirm, type ConfirmRequest } from "../hooks/useConfirm";
import useConfirmedMutation from "../hooks/useConfirmedMutation";
import { Button, SheetFrame, haptic, hasOpenSheet, useAdminBack } from "../ui";
import { postResetUser, postUserBalance } from "./api";
import type { UserAction } from "./format";

const MESSAGE_MAX = 4096;

const TITLE_KEY: Record<UserAction, TranslationKey> = {
  pro: "adminUsers.action.pro",
  balance: "adminUsers.action.balance",
  ban: "adminUsers.action.ban",
  message: "adminUsers.action.message",
  reset: "adminUsers.action.reset",
};

const INPUT =
  "h-9 w-full rounded-xl border border-border bg-surface px-2.5 text-[13px] text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";
const TEXTAREA =
  "w-full rounded-xl border border-border bg-surface px-2.5 py-2 text-[13px] text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold text-muted">{label}</span>
      {children}
    </label>
  );
}

/**
 * Pops the action route — but only once every overlay stacked on top of it
 * (the confirmation dialog) has left the history. Two `navigate(-1)` calls in
 * the same tick are not reliably two steps back, so the close waits for the
 * location to show an empty sheet stack first.
 */
function useDeferredClose(): () => void {
  const location = useLocation();
  const { back } = useAdminBack();
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!pending || hasOpenSheet(location)) return;
    setPending(false);
    back();
  }, [pending, location, back]);

  return useCallback(() => setPending(true), []);
}

export type UserActionSheetProps = {
  user: AdminUserListItem;
  action: UserAction;
};

/**
 * One sheet per action, opened by `/admin/users/:id/action/:action` — so back,
 * Esc and the Telegram BackButton close it and land on the user again.
 *
 * `users.balance` and `wallet.reset_user` are token-confirmed on the server
 * (CONTRACT_P0), so they go through `useConfirmedMutation`; Pro and ban ask
 * first with the same dialog because neither is reversible by accident.
 */
export default function UserActionSheet({ user, action }: UserActionSheetProps) {
  const t = useT();
  const toast = useToast();
  const { formatMoney } = useLocale();
  const queryClient = useQueryClient();
  const { back } = useAdminBack();
  const close = useDeferredClose();

  const [proUnlimited, setProUnlimited] = useState(false);
  const [proDays, setProDays] = useState("30");
  const [proNote, setProNote] = useState("");
  const [amount, setAmount] = useState("");
  const [balanceNote, setBalanceNote] = useState("");
  const [banReason, setBanReason] = useState("");
  const [messageText, setMessageText] = useState("");

  const invalidate = () => {
    // `adminKeys.userDetail` is ["admin","users","detail",id] — one prefix covers both.
    void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
  };

  const proMutation = useMutation({
    mutationFn: (body: { enabled: boolean; days: number | null; note?: string }) =>
      setUserPro(user.user_id, body),
  });

  const banMutation = useMutation({
    mutationFn: (body: { banned: boolean; reason?: string }) => banUser(user.user_id, body),
  });

  const messageMutation = useMutation({
    mutationFn: (text: string) => messageUser(user.user_id, { text }),
  });

  const balance = useConfirmedMutation<{ amount: number; note?: string }, unknown>({
    action: "users.balance",
    paramKeys: ["user_id", "amount"],
    titleKey: "adminUsers.balance.confirmTitle",
    descriptionKey: "adminUsers.balance.confirmDesc",
    successKey: "adminUsers.balance.success",
    invalidate: [["admin", "users"]],
    mutationFn: (body, token) => postUserBalance(user.user_id, body, token),
    onSuccess: close,
  });

  const reset = useConfirmedMutation<{ note?: string }, unknown>({
    action: "wallet.reset_user",
    paramKeys: ["user_id"],
    danger: true,
    titleKey: "adminUsers.reset.confirmTitle",
    descriptionKey: "adminUsers.reset.confirmDesc",
    successKey: "adminUsers.reset.success",
    invalidate: [["admin", "users"]],
    mutationFn: (body, token) => postResetUser(user.user_id, body.note, token),
    onSuccess: close,
  });

  /** Dialog -> request -> close, with the dialog torn down either way. */
  async function confirmed(
    request: ConfirmRequest,
    work: () => Promise<unknown>,
    successKey: TranslationKey,
  ) {
    const ok = await requestConfirm(request);
    if (!ok) return;
    try {
      await work();
      invalidate();
      haptic("success");
      toast.success(t(successKey));
      close();
    } catch (error) {
      haptic("error");
      toast.apiError(error);
    } finally {
      closeConfirm();
    }
  }

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
    void confirmed(
      {
        titleKey: "adminUsers.pro.confirmTitle",
        descriptionKey: enabled ? "adminUsers.pro.confirmGrant" : "adminUsers.pro.confirmRevoke",
        descriptionVars: {
          id: user.user_id,
          term: days === null ? t("adminUsers.badge.unlimited") : t("adminUsers.pro.term", { days }),
        },
        danger: !enabled,
      },
      () => proMutation.mutateAsync({ enabled, days, note }),
      "adminUsers.pro.success",
    );
  }

  function submitBan(banned: boolean) {
    const reason = banReason.trim() || undefined;
    void confirmed(
      {
        titleKey: banned ? "adminUsers.ban.confirmTitle" : "adminUsers.unban.confirmTitle",
        descriptionKey: banned ? "adminUsers.ban.confirmDesc" : "adminUsers.unban.confirmDesc",
        descriptionVars: { id: user.user_id },
        danger: banned,
      },
      () => banMutation.mutateAsync({ banned, reason }),
      banned ? "adminUsers.ban.success" : "adminUsers.unban.success",
    );
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

  async function submitMessage() {
    const text = messageText.trim();
    if (!text) {
      toast.error(t("adminUsers.message.empty"));
      return;
    }
    try {
      await messageMutation.mutateAsync(text.slice(0, MESSAGE_MAX));
      haptic("success");
      toast.success(t("adminUsers.message.success"));
      close();
    } catch (error) {
      haptic("error");
      toast.apiError(error);
    }
  }

  const banned = user.banned;

  const body =
    action === "pro" ? (
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-[13px] font-medium text-text">
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
              className={INPUT}
              value={proDays}
              onChange={(event) => setProDays(event.target.value)}
            />
          </Field>
        )}
        <Field label={t("adminUsers.pro.note")}>
          <input
            type="text"
            className={INPUT}
            value={proNote}
            onChange={(event) => setProNote(event.target.value)}
          />
        </Field>
      </div>
    ) : action === "balance" ? (
      <div className="space-y-2">
        <Field label={t("adminUsers.balance.amount")}>
          <input
            type="number"
            inputMode="numeric"
            className={INPUT}
            placeholder="10000"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </Field>
        <p className="text-[11px] text-muted">{t("adminUsers.balance.hint")}</p>
        <Field label={t("adminUsers.balance.note")}>
          <input
            type="text"
            className={INPUT}
            value={balanceNote}
            onChange={(event) => setBalanceNote(event.target.value)}
          />
        </Field>
      </div>
    ) : action === "ban" ? (
      <div className="space-y-2">
        <p className="text-[13px] text-muted">
          {t(banned ? "adminUsers.unban.confirmDesc" : "adminUsers.ban.confirmDesc", {
            id: user.user_id,
          })}
        </p>
        {!banned && (
          <Field label={t("adminUsers.ban.reason")}>
            <input
              type="text"
              className={INPUT}
              value={banReason}
              onChange={(event) => setBanReason(event.target.value)}
            />
          </Field>
        )}
      </div>
    ) : action === "message" ? (
      <div className="space-y-1">
        <Field label={t("adminUsers.message.text")}>
          <textarea
            rows={5}
            maxLength={MESSAGE_MAX}
            className={TEXTAREA}
            value={messageText}
            onChange={(event) => setMessageText(event.target.value)}
          />
        </Field>
        <p className="text-right text-[11px] tabular-nums text-muted" aria-live="polite">
          {t("adminUsers.message.counter", { count: messageText.length })}
        </p>
      </div>
    ) : (
      <p className="text-[13px] text-danger">
        {t("adminUsers.reset.confirmDesc", { id: user.user_id })}
      </p>
    );

  const footer =
    action === "pro" ? (
      <div className="flex gap-2">
        <Button
          size="md"
          full
          variant="primary"
          labelKey="adminUsers.pro.grant"
          loading={proMutation.isPending}
          onClick={() => submitPro(true)}
        />
        <Button
          size="md"
          variant="danger"
          labelKey="adminUsers.pro.revoke"
          disabled={proMutation.isPending || !user.is_pro}
          onClick={() => submitPro(false)}
        />
      </div>
    ) : action === "balance" ? (
      <Button
        size="md"
        full
        variant="primary"
        labelKey="adminUsers.action.submit"
        loading={balance.isPending}
        disabled={!amount.trim()}
        onClick={submitBalance}
      />
    ) : action === "ban" ? (
      <Button
        size="md"
        full
        variant={banned ? "primary" : "danger"}
        labelKey={banned ? "adminUsers.action.unban" : "adminUsers.action.ban"}
        loading={banMutation.isPending}
        onClick={() => submitBan(!banned)}
      />
    ) : action === "message" ? (
      <Button
        size="md"
        full
        variant="primary"
        labelKey="adminUsers.message.send"
        loading={messageMutation.isPending}
        disabled={!messageText.trim()}
        onClick={() => void submitMessage()}
      />
    ) : (
      <Button
        size="md"
        full
        variant="danger"
        labelKey="adminUsers.action.reset"
        loading={reset.isPending}
        onClick={() =>
          void reset.run({ user_id: user.user_id }, { note: undefined }, { id: user.user_id })
        }
      />
    );

  return (
    <SheetFrame
      open
      onClose={back}
      titleKey={action === "ban" && banned ? "adminUsers.action.unban" : TITLE_KEY[action]}
      subtitle={`#${user.user_id}`}
      footer={footer}
    >
      {body}
    </SheetFrame>
  );
}
