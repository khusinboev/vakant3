import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Settings, Users, Megaphone, Crown, UserX, PlusCircle, ChevronDown, ChevronUp } from "lucide-react";

import client from "../api/client";

type AdminState = {
  is_admin: boolean;
  auto_post_enabled: boolean;
  auto_post_channel: string;
  auto_post_min_salary: number;
  referral_enabled: boolean;
  referral_required_count: number;
  pro_price: number;
  referral_reward: number;
  pro_min_salary: number;
};

// ─── Setting input: placeholder shows current value, type to override ────────
function SettingInput({
  label,
  type = "text",
  currentValue,
  onSave,
  saving,
}: {
  label: string;
  type?: "text" | "number";
  currentValue: string | number;
  onSave: (val: string) => void;
  saving?: boolean;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-slate-500">{label}</label>
      <input
        type={type}
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-1 focus:ring-brand-300"
        placeholder={String(currentValue)}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (draft.trim() !== "") { onSave(draft.trim()); setDraft(""); }
        }}
        disabled={saving}
      />
      <p className="text-[10px] text-slate-400">Joriy: {currentValue}. Bo'sh qolsa o'zgarmaydi.</p>
    </div>
  );
}

// ─── Collapsible section ─────────────────────────────────────────────────────
function Section({
  icon: Icon,
  title,
  children,
  defaultOpen = true,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-slate-500" />
          <span className="text-sm font-semibold text-slate-800">{title}</span>
        </div>
        {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>
      {open && <div className="border-t border-slate-100 px-4 pb-4 pt-3 space-y-4">{children}</div>}
    </div>
  );
}

// ─── Toggle row ───────────────────────────────────────────────────────────────
function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between">
      <span className="text-sm text-slate-700">{label}</span>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${checked ? "bg-emerald-500" : "bg-slate-300"}`}
      >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${checked ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </label>
  );
}

export default function Admin() {
  const state = useQuery({
    queryKey: ["admin", "state"],
    queryFn: async () => {
      const { data } = await client.get<AdminState>("/admin/state");
      return data;
    },
    retry: false,
  });

  const [local, setLocal] = useState<AdminState | null>(null);

  // User management state
  const [addUserId, setAddUserId] = useState("");
  const [addAmount, setAddAmount] = useState("");
  const [addMsg, setAddMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [resetUserId, setResetUserId] = useState("");
  const [resetMsg, setResetMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [resetConfirm, setResetConfirm] = useState(false);

  const patch = useMutation({
    mutationFn: async (payload: Partial<AdminState>) => {
      const { data } = await client.patch<AdminState>("/admin/state", payload);
      return data;
    },
    onSuccess: (data) => {
      setLocal(data);
      void state.refetch();
    },
  });

  const addBalance = useMutation({
    mutationFn: async () => {
      const amount = Number(addAmount);
      if (!amount || amount <= 0) throw new Error("Noto'g'ri miqdor");
      const { data } = await client.post<{ ok: boolean; new_balance: number }>("/wallet/admin/add-balance", {
        user_id: Number(addUserId),
        amount,
      });
      return data;
    },
    onSuccess: (data) => {
      setAddMsg({ ok: true, text: `✓ Yangi balans: ${data.new_balance.toLocaleString("uz-UZ")} so'm` });
      setAddUserId("");
      setAddAmount("");
    },
    onError: (err: any) => {
      setAddMsg({ ok: false, text: err?.message || err?.response?.data?.detail || "Xatolik" });
    },
  });

  const resetUser = useMutation({
    mutationFn: async () => {
      const { data } = await client.post<{ ok: boolean }>("/wallet/admin/reset-user", {
        user_id: Number(resetUserId),
      });
      return data;
    },
    onSuccess: () => {
      setResetMsg({ ok: true, text: `✓ ${resetUserId} ID: balans=0, pro=off` });
      setResetUserId("");
      setResetConfirm(false);
    },
    onError: (err: any) => {
      setResetMsg({ ok: false, text: err?.response?.data?.detail || "Xatolik" });
      setResetConfirm(false);
    },
  });

  const s = local || state.data;

  if (state.isLoading && !s) return <div className="card p-4 text-sm">Yuklanmoqda...</div>;
  if (state.isError || !s) {
    return <div className="card p-4 text-sm text-red-600">Admin panel faqat adminlar uchun.</div>;
  }

  const saving = patch.isPending;

  return (
    <div className="space-y-3">
      {/* Auto-post */}
      <Section icon={Megaphone} title="Auto-post sozlamalari">
        <ToggleRow
          label="Auto-post faol"
          checked={s.auto_post_enabled}
          onChange={(v) => patch.mutate({ auto_post_enabled: v })}
        />
        <SettingInput
          label="Kanal (@username yoki -100...)"
          type="text"
          currentValue={s.auto_post_channel}
          onSave={(v) => patch.mutate({ auto_post_channel: v })}
          saving={saving}
        />
        <SettingInput
          label="Minimal maosh chegarasi (so'm)"
          type="number"
          currentValue={s.auto_post_min_salary}
          onSave={(v) => patch.mutate({ auto_post_min_salary: Number(v) })}
          saving={saving}
        />
      </Section>

      {/* Referral gate */}
      <Section icon={Settings} title="Referral gate" defaultOpen={false}>
        <ToggleRow
          label="Referral gate faol"
          checked={s.referral_enabled}
          onChange={(v) => patch.mutate({ referral_enabled: v })}
        />
        <SettingInput
          label="Talab qilinadigan referral soni"
          type="number"
          currentValue={s.referral_required_count}
          onSave={(v) => patch.mutate({ referral_required_count: Number(v) })}
          saving={saving}
        />
      </Section>

      {/* Pro tariff settings */}
      <Section icon={Crown} title="Pro tarif sozlamalari">
        <SettingInput
          label="Pro tarif narxi (so'm)"
          type="number"
          currentValue={s.pro_price}
          onSave={(v) => patch.mutate({ pro_price: Number(v) })}
          saving={saving}
        />
        <SettingInput
          label="Referral mukofoti (so'm)"
          type="number"
          currentValue={s.referral_reward}
          onSave={(v) => patch.mutate({ referral_reward: Number(v) })}
          saving={saving}
        />
        <SettingInput
          label="Pro minimal maosh chegarasi (so'm)"
          type="number"
          currentValue={s.pro_min_salary}
          onSave={(v) => patch.mutate({ pro_min_salary: Number(v) })}
          saving={saving}
        />
      </Section>

      {/* User management */}
      <Section icon={Users} title="Foydalanuvchi boshqaruvi">
        {/* Add balance */}
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 flex items-center gap-1">
            <PlusCircle size={12} /> Balans qo'shish
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-slate-400">Telegram ID</label>
              <input
                type="number"
                className="mt-0.5 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-emerald-400 focus:outline-none"
                placeholder="123456789"
                value={addUserId}
                onChange={(e) => { setAddUserId(e.target.value); setAddMsg(null); }}
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-400">Miqdor (so'm)</label>
              <input
                type="number"
                className="mt-0.5 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-emerald-400 focus:outline-none"
                placeholder="10000"
                value={addAmount}
                onChange={(e) => { setAddAmount(e.target.value); setAddMsg(null); }}
              />
            </div>
          </div>
          {addUserId && addAmount && Number(addAmount) > 0 && (
            <p className="rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-800">
              ID <strong>{addUserId}</strong> ga <strong>{Number(addAmount).toLocaleString("uz-UZ")} so'm</strong> qo'shiladi
            </p>
          )}
          {addMsg && (
            <p className={`text-xs font-medium ${addMsg.ok ? "text-emerald-600" : "text-red-500"}`}>{addMsg.text}</p>
          )}
          <button
            className="tap-target w-full rounded-2xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            disabled={addBalance.isPending || !addUserId || !addAmount || Number(addAmount) <= 0}
            onClick={() => addBalance.mutate()}
          >
            {addBalance.isPending ? "Qo'shilmoqda..." : "Balans qo'shish"}
          </button>
        </div>

        <div className="border-t border-slate-100" />

        {/* Reset user */}
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-red-500 flex items-center gap-1">
            <UserX size={12} /> Foydalanuvchini tozalash (balans=0, pro=off)
          </p>
          <div>
            <label className="text-[10px] text-slate-400">Telegram ID</label>
            <input
              type="number"
              className="mt-0.5 w-full rounded-xl border border-red-200 px-3 py-2 text-sm focus:border-red-400 focus:outline-none"
              placeholder="123456789"
              value={resetUserId}
              onChange={(e) => { setResetUserId(e.target.value); setResetMsg(null); setResetConfirm(false); }}
            />
          </div>
          {resetMsg && (
            <p className={`text-xs font-medium ${resetMsg.ok ? "text-emerald-600" : "text-red-500"}`}>{resetMsg.text}</p>
          )}
          {!resetConfirm ? (
            <button
              className="tap-target w-full rounded-2xl border border-red-300 px-4 py-2.5 text-sm font-semibold text-red-600 disabled:opacity-50"
              disabled={!resetUserId}
              onClick={() => setResetConfirm(true)}
            >
              Tozalash
            </button>
          ) : (
            <div className="space-y-2">
              <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                ⚠️ ID <strong>{resetUserId}</strong> — balans 0 ga tushiriladi, Pro olib qo'yiladi. Tasdiqlaysizmi?
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  className="tap-target rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600"
                  onClick={() => setResetConfirm(false)}
                >
                  Bekor
                </button>
                <button
                  className="tap-target rounded-2xl bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  disabled={resetUser.isPending}
                  onClick={() => resetUser.mutate()}
                >
                  {resetUser.isPending ? "..." : "Ha, tozala"}
                </button>
              </div>
            </div>
          )}
        </div>
      </Section>

      {saving && <p className="text-center text-xs text-slate-400">Saqlanmoqda...</p>}
    </div>
  );
}

