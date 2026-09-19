import { useState } from "react";
import { PlusCircle, Search, UserX } from "lucide-react";

import useToast from "../../../hooks/useToast";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import GroupCard from "../components/GroupCard";
import { useAddBalance, useInspectResumeUser, useResetUser } from "../useAdminQueries";
import type { ResumeUserInspect } from "../types";

/** A Telegram id is a positive integer; anything else is a typo, not a request. */
function parseUserId(raw: string): number | null {
  const value = Number(raw.trim());
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

const INPUT_CLASS =
  "mt-0.5 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

export default function UsersTab() {
  const t = useT();
  const toast = useToast();
  const { formatMoney, formatNumber, formatDateTime } = useLocale();

  const [addUserId, setAddUserId] = useState("");
  const [addAmount, setAddAmount] = useState("");
  const [resetUserId, setResetUserId] = useState("");
  const [resetConfirm, setResetConfirm] = useState(false);
  const [inspectUserId, setInspectUserId] = useState("");
  const [inspectResult, setInspectResult] = useState<ResumeUserInspect | null>(null);

  const addBalance = useAddBalance();
  const resetUser = useResetUser();
  const inspectUser = useInspectResumeUser();

  const addAmountValue = Number(addAmount.trim());
  const addPreviewVisible =
    addUserId.trim() !== "" && Number.isSafeInteger(addAmountValue) && addAmountValue > 0;

  function submitAddBalance() {
    const userId = parseUserId(addUserId);
    if (userId === null) {
      toast.error(t("admin.users.invalidId"));
      return;
    }
    if (!Number.isSafeInteger(addAmountValue) || addAmountValue <= 0) {
      toast.error(t("admin.users.invalidAmount"));
      return;
    }
    addBalance.mutate(
      { userId, amount: addAmountValue },
      {
        onSuccess: (data) => {
          toast.success(t("admin.users.addSuccess", { balance: formatMoney(data.new_balance) }));
          setAddUserId("");
          setAddAmount("");
        },
        onError: (error) => toast.apiError(error),
      },
    );
  }

  function submitInspect() {
    const userId = parseUserId(inspectUserId);
    if (userId === null) {
      toast.error(t("admin.users.invalidId"));
      return;
    }
    inspectUser.mutate(userId, {
      onSuccess: (data) => setInspectResult(data),
      onError: (error) => {
        setInspectResult(null);
        toast.apiError(error);
      },
    });
  }

  function submitReset() {
    const userId = parseUserId(resetUserId);
    if (userId === null) {
      toast.error(t("admin.users.invalidId"));
      setResetConfirm(false);
      return;
    }
    resetUser.mutate(userId, {
      onSuccess: () => {
        toast.success(t("admin.danger.success", { id: userId }));
        setResetUserId("");
        setResetConfirm(false);
      },
      onError: (error) => {
        toast.apiError(error);
        setResetConfirm(false);
      },
    });
  }

  return (
    <div className="space-y-4">
      <GroupCard icon={PlusCircle} title={t("admin.users.addTitle")} accent="success" divide={false}>
        <div className="space-y-3 pb-4 pt-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-medium text-muted" htmlFor="admin-add-user">
                {t("admin.users.telegramId")}
              </label>
              <input
                id="admin-add-user"
                type="number"
                inputMode="numeric"
                className={INPUT_CLASS}
                placeholder="123456789"
                value={addUserId}
                onChange={(event) => setAddUserId(event.target.value)}
              />
            </div>
            <div>
              <label className="text-[10px] font-medium text-muted" htmlFor="admin-add-amount">
                {t("admin.users.amount")}
              </label>
              <input
                id="admin-add-amount"
                type="number"
                inputMode="numeric"
                className={INPUT_CLASS}
                placeholder="10000"
                value={addAmount}
                onChange={(event) => setAddAmount(event.target.value)}
              />
            </div>
          </div>
          {addPreviewVisible && (
            <p className="rounded-xl bg-warning/10 px-3 py-2 text-xs text-warning">
              {t("admin.users.addPreview", {
                id: addUserId.trim(),
                amount: formatMoney(addAmountValue),
              })}
            </p>
          )}
          <button
            type="button"
            className="tap-target w-full rounded-2xl bg-success py-2.5 text-sm font-semibold text-white disabled:opacity-50 dark:text-bg"
            disabled={addBalance.isPending || !addPreviewVisible}
            onClick={submitAddBalance}
          >
            {addBalance.isPending ? t("admin.users.adding") : t("admin.users.addSubmit")}
          </button>
        </div>
      </GroupCard>

      <GroupCard icon={Search} title={t("admin.users.inspectTitle")} divide={false}>
        <div className="space-y-3 py-3">
          <div className="flex gap-2">
            <input
              type="number"
              inputMode="numeric"
              aria-label={t("admin.users.inspectPlaceholder")}
              className={`min-w-0 flex-1 ${INPUT_CLASS}`}
              placeholder={t("admin.users.inspectPlaceholder")}
              value={inspectUserId}
              onChange={(event) => setInspectUserId(event.target.value)}
            />
            <button
              type="button"
              className="tap-target shrink-0 rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primaryFg disabled:opacity-50"
              disabled={!inspectUserId.trim() || inspectUser.isPending}
              onClick={submitInspect}
            >
              {inspectUser.isPending ? "…" : t("admin.users.inspectSubmit")}
            </button>
          </div>

          {inspectResult && (
            <div className="space-y-3 rounded-xl border border-border bg-surfaceAlt p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-text">
                    {inspectResult.first_name || `ID: ${inspectResult.user_id}`}
                  </p>
                  <p className="truncate text-xs text-muted">
                    @{inspectResult.username || "–"} · {inspectResult.user_id}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                    inspectResult.has_resume
                      ? "bg-success/15 text-success"
                      : "bg-surface text-muted"
                  }`}
                >
                  {inspectResult.has_resume
                    ? t("admin.users.hasResume")
                    : t("admin.users.noResume")}
                </span>
              </div>

              <div className="space-y-1 rounded-lg border border-border bg-surface p-2.5">
                {inspectResult.selected_template && (
                  <div className="flex justify-between gap-2">
                    <span className="text-[11px] text-muted">{t("admin.users.template")}</span>
                    <span className="text-right text-[11px] font-medium text-text">
                      {inspectResult.selected_template}
                    </span>
                  </div>
                )}
                {inspectResult.updated_at !== null && (
                  <div className="flex justify-between gap-2">
                    <span className="text-[11px] text-muted">{t("admin.users.updatedAt")}</span>
                    <span className="text-right text-[11px] font-medium text-text">
                      {formatDateTime(inspectResult.updated_at)}
                    </span>
                  </div>
                )}
                {Object.entries(inspectResult.profile_preview ?? {}).map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-2">
                    <span className="text-[11px] text-muted">{key}</span>
                    <span className="text-right text-[11px] font-medium text-text">
                      {typeof value === "number" ? formatNumber(value) : String(value)}
                    </span>
                  </div>
                ))}
              </div>

              <div>
                <p className="mb-1.5 text-[11px] font-semibold text-muted">
                  {t("admin.users.recentEvents")}
                </p>
                {inspectResult.recent_events.length === 0 ? (
                  <p className="text-[11px] text-muted">{t("admin.users.noEvents")}</p>
                ) : (
                  <ul className="space-y-1">
                    {inspectResult.recent_events.slice(0, 8).map((event, index) => (
                      <li
                        key={`${event.event_name}-${event.created_at}-${index}`}
                        className="text-[11px] text-text"
                      >
                        <span className="font-medium">{event.event_name}</span>
                        {event.step ? ` (${event.step})` : ""}
                        {" · "}
                        <span className="text-muted">{formatDateTime(event.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </div>
      </GroupCard>

      <section className="card overflow-hidden border-danger/40">
        <header className="flex items-center gap-2.5 border-b border-danger/30 bg-danger/10 px-4 py-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-danger/15">
            <UserX size={14} className="text-danger" aria-hidden="true" />
          </span>
          <h2 className="text-sm font-semibold text-danger">{t("admin.danger.title")}</h2>
        </header>
        <div className="space-y-3 p-4">
          <p className="text-xs text-muted">{t("admin.danger.desc")}</p>
          <div>
            <label className="text-[10px] font-medium text-muted" htmlFor="admin-reset-user">
              {t("admin.users.telegramId")}
            </label>
            <input
              id="admin-reset-user"
              type="number"
              inputMode="numeric"
              className={INPUT_CLASS}
              placeholder="123456789"
              value={resetUserId}
              onChange={(event) => {
                setResetUserId(event.target.value);
                setResetConfirm(false);
              }}
            />
          </div>
          {!resetConfirm ? (
            <button
              type="button"
              className="tap-target w-full rounded-2xl border-2 border-danger/50 py-2.5 text-sm font-semibold text-danger disabled:opacity-40"
              disabled={!resetUserId.trim()}
              onClick={() => setResetConfirm(true)}
            >
              {t("admin.danger.submit")}
            </button>
          ) : (
            <div className="space-y-3">
              <p role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-xs text-danger">
                ⚠️ {t("admin.danger.confirm", { id: resetUserId.trim() })}
              </p>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  className="tap-target rounded-2xl border border-border py-2.5 text-sm font-semibold text-muted"
                  onClick={() => setResetConfirm(false)}
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="button"
                  className="tap-target rounded-2xl bg-danger py-2.5 text-sm font-semibold text-white disabled:opacity-50 dark:text-bg"
                  disabled={resetUser.isPending}
                  onClick={submitReset}
                >
                  {resetUser.isPending ? "…" : t("admin.danger.confirmYes")}
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
