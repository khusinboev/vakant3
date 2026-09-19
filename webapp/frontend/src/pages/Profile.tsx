import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Bookmark, ChevronDown, Crown, Share2, Users, Wallet } from "lucide-react";

import client from "../api/client";
import BottomSheet from "../components/ui/BottomSheet";
import SettingsCard from "../components/Settings/SettingsCard";
import { useSaves } from "../hooks/useSaves";
import { useRegions, useSpecs, regionName } from "../hooks/useStaticList";
import useToast from "../hooks/useToast";
import { useT } from "../i18n/useT";
import { useLocale } from "../i18n/useLocale";
import { parseApiError } from "../lib/parseApiError";
import { shareRefLink } from "../lib/share";
import { useAuthStore } from "../store/auth";

type WalletData = { balance: number; is_pro: boolean; pro_price: number; referral_reward: number };
type ReferralStats = {
  current: number;
  required: number;
  enabled: boolean;
  unlocked: boolean;
  ref_link: string;
};

export default function Profile() {
  const navigate = useNavigate();
  const t = useT();
  const { formatNumber } = useLocale();
  const toast = useToast();
  const queryClient = useQueryClient();

  const authUser = useAuthStore((s) => s.user);
  const webApp = window.Telegram?.WebApp;
  const tgUser = webApp?.initDataUnsafe?.user;

  // ─── Hooks — all unconditional, the branching happens in the JSX below ─────
  const saves = useSaves(1, 1, true);
  const savesCount = saves.list.data?.total ?? 0;

  const referralStats = useQuery<ReferralStats>({
    queryKey: ["referral", "stats"],
    queryFn: async () => {
      const { data } = await client.get<ReferralStats>("/referral/stats");
      return data;
    },
    retry: false,
  });

  const wallet = useQuery<WalletData>({
    queryKey: ["wallet"],
    queryFn: async () => {
      const { data } = await client.get<WalletData>("/wallet");
      return data;
    },
    retry: false,
  });

  const notifQuery = useQuery({
    queryKey: ["notification-settings", authUser?.user_id],
    queryFn: async () => {
      const { data } = await client.get<{ enabled: boolean }>("/notifications/settings");
      return data;
    },
    retry: 2,
    staleTime: 30_000,
  });

  const [proModal, setProModal] = useState(false);
  const [filterModal, setFilterModal] = useState(false);
  const [filterRegion, setFilterRegion] = useState("");
  const [filterSpecs, setFilterSpecs] = useState("");
  const [filterMinSalary, setFilterMinSalary] = useState("");
  const [regionOpen, setRegionOpen] = useState(false);

  const regionsQuery = useRegions();
  const specsQuery = useSpecs();

  const saveFiltersMutation = useMutation({
    mutationFn: (payload: { region?: string; money?: number; specs?: string }) =>
      client.patch("/profile/filters", payload),
  });

  const notifKey = ["notification-settings", authUser?.user_id];
  const toggleNotif = useMutation({
    mutationFn: () => client.post<{ enabled: boolean }>("/notifications/toggle"),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: notifKey });
      const prev = queryClient.getQueryData<{ enabled: boolean }>(notifKey);
      queryClient.setQueryData(notifKey, { enabled: !(prev?.enabled ?? false) });
      return { prev };
    },
    onSuccess: (res) => {
      queryClient.setQueryData(notifKey, { enabled: res.data.enabled });
      void queryClient.invalidateQueries({ queryKey: notifKey });
    },
    onError: (error: unknown, _vars, context) => {
      // Always rollback — if prev was undefined (query not loaded), restore to disabled
      queryClient.setQueryData(notifKey, context?.prev ?? { enabled: false });
      if (parseApiError(error).code === "PRO_REQUIRED") setProModal(true);
      else toast.apiError(error);
    },
  });

  // ─── Derived ───────────────────────────────────────────────────────────────
  const user = tgUser
    ? {
        id: tgUser.id,
        first_name: tgUser.first_name,
        last_name: tgUser.last_name,
        username: tgUser.username,
        photo_url: tgUser.photo_url,
      }
    : authUser
      ? {
          id: authUser.user_id,
          first_name: authUser.first_name,
          last_name: "",
          username: authUser.username ?? undefined,
          photo_url: authUser.photo_url ?? undefined,
        }
      : null;

  const fullName = user ? [user.first_name, user.last_name].filter(Boolean).join(" ") : "";
  const refCount = referralStats.data?.current ?? 0;
  const refLink = referralStats.data?.ref_link;
  const balance = wallet.data?.balance ?? 0;
  const isPro = wallet.data?.is_pro ?? false;
  const notifEnabled = notifQuery.data?.enabled ?? false;

  function handleToggleClick() {
    if (toggleNotif.isPending || saveFiltersMutation.isPending) return;
    if (!notifEnabled) {
      if (!isPro) {
        setProModal(true);
        return;
      }
      setFilterModal(true);
    } else {
      toggleNotif.mutate();
    }
  }

  async function handleFilterConfirm() {
    setFilterModal(false);
    const payload: { region?: string; money?: number; specs?: string } = {};
    if (filterRegion) payload.region = filterRegion;
    if (filterSpecs) payload.specs = filterSpecs;
    const salary = parseInt(filterMinSalary, 10);
    if (!Number.isNaN(salary) && salary > 0) payload.money = salary;
    try {
      if (Object.keys(payload).length > 0) await saveFiltersMutation.mutateAsync(payload);
    } catch {
      // filter save failure is non-blocking — still enable notifications
    }
    toggleNotif.mutate();
  }

  // ─── Render ────────────────────────────────────────────────────────────────
  if (!webApp) {
    return (
      <div className="card p-6 text-center">
        <p className="text-base font-semibold text-text">{t("profile.title")}</p>
        <p className="mt-2 text-sm text-muted">{t("profile.tgOnly")}</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="card p-6 text-center">
        <p className="text-base font-semibold text-text">{t("profile.title")}</p>
        <p className="mt-2 text-sm text-muted">{t("profile.userNotFound")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Hero */}
      <section className="card overflow-hidden p-0">
        <div className="bg-gradient-to-br from-brand-700 to-brand-900 px-5 pb-4 pt-6 text-white">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 shrink-0 overflow-hidden rounded-full border-2 border-white/20 bg-white/10">
              {user.photo_url ? (
                <img src={user.photo_url} alt={fullName} className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-2xl font-bold text-white/70">
                  {(user.first_name?.[0] || "U").toUpperCase()}
                </div>
              )}
            </div>
            <div className="min-w-0">
              <p className="text-lg font-bold leading-tight">{fullName || t("profile.tgUser")}</p>
              <p className="text-sm text-white/70">
                {user.username ? `@${user.username}` : `ID: ${user.id}`}
              </p>
              <div className="mt-2">
                {isPro ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-0.5 text-xs font-bold text-black/80">
                    <Crown size={11} /> {t("profile.pro")}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-0.5 text-xs font-medium text-white/80">
                    {t("profile.free")}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 divide-x divide-border bg-surface">
          <div className="flex flex-col items-center py-3 text-center">
            <p className="text-lg font-bold text-text">{saves.list.isLoading ? "—" : savesCount}</p>
            <p className="text-[11px] text-muted">{t("profile.statSaved")}</p>
          </div>
          <div className="flex flex-col items-center py-3 text-center">
            <p className="text-lg font-bold text-text">{referralStats.isLoading ? "—" : refCount}</p>
            <p className="text-[11px] text-muted">{t("profile.statReferrals")}</p>
          </div>
          <div className="flex flex-col items-center py-3 text-center">
            <p className="text-lg font-bold text-text">
              {wallet.isLoading ? "—" : formatNumber(balance)}
            </p>
            <p className="text-[11px] text-muted">{t("profile.statBalance")}</p>
          </div>
        </div>
      </section>

      {/* Quick actions */}
      <section className="grid grid-cols-2 gap-3">
        <button
          type="button"
          className="card tap-target flex flex-col items-center gap-2 p-4 text-center"
          onClick={() => navigate("/saves")}
        >
          <div className="rounded-full bg-surfaceAlt p-3">
            <Bookmark size={18} className="text-text" />
          </div>
          <p className="text-sm font-semibold text-text">{t("profile.savedJobs")}</p>
          <p className="text-xs text-muted">
            {saves.list.isLoading ? "..." : t("common.itemsCount", { n: savesCount })}
          </p>
        </button>

        <button
          type="button"
          className="card tap-target flex flex-col items-center gap-2 p-4 text-center"
          onClick={() => navigate("/wallet")}
        >
          <div className="rounded-full bg-warning/10 p-3">
            <Wallet size={18} className={isPro ? "text-warning" : "text-muted"} />
          </div>
          <p className="text-sm font-semibold text-text">{t("profile.wallet")}</p>
          <p className="text-xs text-muted">
            {wallet.isLoading ? "..." : `${formatNumber(balance)} ${t("common.sum")}`}
          </p>
        </button>
      </section>

      {/* Referral invite */}
      <section className="card p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-success" />
            <h3 className="text-sm font-semibold text-text">{t("profile.inviteTitle")}</h3>
          </div>
          <span className="shrink-0 rounded-full bg-success/15 px-2 py-0.5 text-xs font-bold text-success">
            {t("referral.rewardAmount", { amount: formatNumber(wallet.data?.referral_reward ?? 2000) })}
          </span>
        </div>
        <p className="mt-2 text-xs text-muted">{t("profile.inviteBody")}</p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            className="tap-target flex flex-1 items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primaryFg"
            onClick={() => refLink && shareRefLink(refLink, t("referral.shareText"))}
          >
            <Share2 size={15} />
            {t("common.share")}
          </button>
          <button
            type="button"
            className="tap-target rounded-2xl border border-border px-4 py-3 text-sm font-semibold text-text"
            onClick={() => navigate("/referral")}
          >
            {t("common.statistics")}
          </button>
        </div>
      </section>

      {/* Referral gate status (if enabled) */}
      {referralStats.data?.enabled && (
        <section className="card p-4">
          <h3 className="text-sm font-semibold text-text">{t("profile.gateTitle")}</h3>
          <div className="mt-2 flex items-center justify-between rounded-xl bg-surfaceAlt px-3 py-2 text-sm">
            <span className="text-muted">{t("profile.gateReferrals")}</span>
            <span className={`font-semibold ${referralStats.data.unlocked ? "text-success" : "text-warning"}`}>
              {referralStats.data.current}/{referralStats.data.required}
              {referralStats.data.unlocked ? " ✓" : ""}
            </span>
          </div>
        </section>
      )}

      {/* Notification toggle */}
      <section className="card p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Bell
              size={16}
              className={
                notifQuery.isLoading ? "text-muted/50" : notifEnabled ? "text-primary" : "text-muted"
              }
            />
            <h3 className="text-sm font-semibold text-text">{t("profile.notifications")}</h3>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={notifEnabled}
            aria-label={t("profile.notifToggleAria")}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-200 ${
              notifEnabled ? "bg-primary" : "bg-border"
            } ${toggleNotif.isPending ? "opacity-60" : ""}`}
            onClick={handleToggleClick}
            disabled={toggleNotif.isPending || saveFiltersMutation.isPending}
          >
            <span
              className={`absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${
                notifEnabled ? "translate-x-5" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
        <p className="mt-2 text-xs text-muted">
          {notifEnabled
            ? t("profile.notifOn")
            : isPro
              ? t("profile.notifOffPro")
              : t("profile.notifOffFree")}
        </p>
        {!isPro && (
          <button
            type="button"
            className="tap-target mt-3 w-full rounded-2xl border border-warning/30 bg-warning/10 py-2.5 text-xs font-semibold text-warning"
            onClick={() => navigate("/wallet")}
          >
            💎 {t("home.goPro")}
          </button>
        )}
      </section>

      <SettingsCard />

      {/* Filter sheet (shown before enabling notifications) */}
      <BottomSheet
        open={filterModal}
        onClose={() => setFilterModal(false)}
        title={t("profile.notifSettings")}
        subtitle={t("profile.notifSettingsBody")}
        footer={
          <div className="flex flex-col gap-2">
            <button
              type="button"
              className="tap-target w-full rounded-2xl bg-primary py-3 text-sm font-semibold text-primaryFg disabled:opacity-60"
              onClick={() => void handleFilterConfirm()}
              disabled={toggleNotif.isPending || saveFiltersMutation.isPending}
            >
              {toggleNotif.isPending || saveFiltersMutation.isPending
                ? t("common.saving")
                : t("profile.enableNotif")}
            </button>
            <button
              type="button"
              className="tap-target w-full rounded-2xl bg-surfaceAlt py-3 text-sm font-medium text-text"
              onClick={() => setFilterModal(false)}
            >
              {t("common.cancel")}
            </button>
          </div>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">
              {t("profile.region")} ({t("common.optional")})
            </label>
            <div className="relative">
              <button
                type="button"
                aria-expanded={regionOpen}
                className="flex w-full items-center justify-between rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-text"
                onClick={() => setRegionOpen((o) => !o)}
              >
                <span>
                  {regionsQuery.data?.find((r) => r.soato === filterRegion)
                    ? regionName(regionsQuery.data.find((r) => r.soato === filterRegion)!)
                    : t("filters.allRegions")}
                </span>
                <ChevronDown
                  size={14}
                  className={`flex-shrink-0 text-muted transition-transform duration-150 ${regionOpen ? "rotate-180" : ""}`}
                />
              </button>
              {regionOpen && (
                <div className="absolute left-0 right-0 top-full z-10 mt-1 max-h-52 overflow-y-auto rounded-xl border border-border bg-surface shadow-xl">
                  <button
                    type="button"
                    className="w-full border-b border-border px-3 py-2.5 text-left text-sm text-muted"
                    onClick={() => {
                      setFilterRegion("");
                      setRegionOpen(false);
                    }}
                  >
                    {t("filters.allRegions")}
                  </button>
                  {regionsQuery.data?.map((r) => (
                    <button
                      type="button"
                      key={r.soato}
                      className={`w-full border-b border-border px-3 py-2.5 text-left text-sm last:border-0 ${
                        filterRegion === r.soato ? "bg-primary/10 font-medium text-primary" : "text-text"
                      }`}
                      onClick={() => {
                        setFilterRegion(r.soato);
                        setRegionOpen(false);
                      }}
                    >
                      {regionName(r)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted">
              {t("profile.sector")} ({t("common.optional")})
            </label>
            <div className="flex flex-wrap gap-2">
              {specsQuery.data?.map((s) => (
                <button
                  type="button"
                  key={s.id}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    filterSpecs === s.id
                      ? "border-primary bg-primary text-primaryFg"
                      : "border-border bg-surface text-text"
                  }`}
                  onClick={() => setFilterSpecs(filterSpecs === s.id ? "" : s.id)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted" htmlFor="notif-min-salary">
              {t("profile.minSalary")} ({t("common.optional")})
            </label>
            <input
              id="notif-min-salary"
              type="text"
              inputMode="numeric"
              className="w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-text outline-none focus:border-primary"
              value={filterMinSalary ? filterMinSalary.replace(/\B(?=(\d{3})+(?!\d))/g, " ") : ""}
              onChange={(e) => setFilterMinSalary(e.target.value.replace(/\D/g, ""))}
              placeholder={t("profile.minSalaryPlaceholder")}
            />
          </div>
        </div>
      </BottomSheet>

      {/* Pro required sheet */}
      <BottomSheet open={proModal} onClose={() => setProModal(false)} ariaLabel={t("profile.proNotifTitle")}>
        <div className="text-center">
          <div className="mb-3 text-3xl">🔔</div>
          <p className="text-base font-bold text-text">{t("profile.proNotifTitle")}</p>
          <p className="mt-1 text-sm text-muted">{t("profile.proNotifBody")}</p>
          <div className="mt-4 flex flex-col gap-2">
            <button
              type="button"
              className="tap-target w-full rounded-2xl bg-primary py-3 text-sm font-semibold text-primaryFg"
              onClick={() => {
                setProModal(false);
                navigate("/wallet");
              }}
            >
              💎 {t("home.goPro")}
            </button>
            <button
              type="button"
              className="tap-target w-full rounded-2xl bg-surfaceAlt py-3 text-sm font-medium text-text"
              onClick={() => setProModal(false)}
            >
              {t("common.close")}
            </button>
          </div>
        </div>
      </BottomSheet>
    </div>
  );
}
