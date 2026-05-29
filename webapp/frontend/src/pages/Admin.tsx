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
  resume_target_creation_minutes: number;
  resume_target_completion_rate: number;
  resume_target_send_success_rate: number;
  resume_target_export_success_rate: number;
};

type ResumeMetrics = {
  opened_24h: number;
  ready_24h: number;
  save_success_24h: number;
  save_error_24h: number;
  send_success_24h: number;
  send_error_24h: number;
  export_success_24h: number;
  export_error_24h: number;
  unique_users_24h: number;
  avg_ttfi_ms: number;
  avg_save_latency_ms: number;
  avg_send_latency_ms: number;
  avg_export_latency_ms: number;
};

type ResumeFunnelStep = {
  step: string;
  entered_users: number;
  completed_users: number;
  dropoff_users: number;
  completion_rate: number;
};

type ResumeFunnel = {
  window_hours: number;
  steps: ResumeFunnelStep[];
};

type ResumeUserInspect = {
  user_id: number;
  first_name: string;
  username: string;
  has_resume: boolean;
  selected_template: string;
  updated_at: number | null;
  profile_preview: Record<string, string | number>;
  recent_events: Array<{ event_name: string; step?: string | null; created_at: number }>;
};

type ResumeDiagnostics = {
  items: Array<{
    source: string;
    status: string;
    error_text: string;
    count_24h: number;
    last_seen_at: number;
  }>;
};

type ResumeGoals = {
  window_hours: number;
  opened_users: number;
  completed_users: number;
  send_attempts: number;
  pdf_export_attempts: number;
  median_creation_minutes: number;
  completion_rate: number;
  send_success_rate: number;
  pdf_export_success_rate: number;
  creation_time_target_minutes: number;
  completion_rate_target: number;
  send_success_rate_target: number;
  pdf_export_success_rate_target: number;
  creation_time_ok: boolean;
  completion_rate_ok: boolean;
  send_success_rate_ok: boolean;
  pdf_export_success_rate_ok: boolean;
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
  defaultOpen = false,
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
  const [inspectUserId, setInspectUserId] = useState("");
  const [inspectResult, setInspectResult] = useState<ResumeUserInspect | null>(null);
  const [inspectError, setInspectError] = useState("");

  const resumeMetrics = useQuery({
    queryKey: ["admin", "resume-metrics"],
    queryFn: async () => {
      const { data } = await client.get<ResumeMetrics>("/admin/resume-metrics");
      return data;
    },
    retry: false,
  });

  const resumeFunnel = useQuery({
    queryKey: ["admin", "resume-funnel"],
    queryFn: async () => {
      const { data } = await client.get<ResumeFunnel>("/admin/resume-funnel");
      return data;
    },
    retry: false,
  });

  const resumeDiagnostics = useQuery({
    queryKey: ["admin", "resume-diagnostics"],
    queryFn: async () => {
      const { data } = await client.get<ResumeDiagnostics>("/admin/resume-diagnostics");
      return data;
    },
    retry: false,
  });

  const resumeGoals = useQuery({
    queryKey: ["admin", "resume-goals"],
    queryFn: async () => {
      const { data } = await client.get<ResumeGoals>("/admin/resume-goals");
      return data;
    },
    retry: false,
  });

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

  const inspectResumeUser = useMutation({
    mutationFn: async (userId: number) => {
      const { data } = await client.get<ResumeUserInspect>(`/admin/resume-user/${userId}`);
      return data;
    },
    onSuccess: (data) => {
      setInspectResult(data);
      setInspectError("");
    },
    onError: (err: any) => {
      setInspectResult(null);
      setInspectError(err?.response?.data?.detail || "Foydalanuvchi topilmadi");
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
      <Section icon={Settings} title="Referral gate">
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

      <Section icon={Settings} title="Resume KPI target sozlamalari">
        <SettingInput
          label="Median creation time target (daq)"
          type="number"
          currentValue={s.resume_target_creation_minutes}
          onSave={(v) => patch.mutate({ resume_target_creation_minutes: Number(v) })}
          saving={saving}
        />
        <SettingInput
          label="Completion rate target (%)"
          type="number"
          currentValue={s.resume_target_completion_rate}
          onSave={(v) => patch.mutate({ resume_target_completion_rate: Number(v) })}
          saving={saving}
        />
        <SettingInput
          label="Send success target (%)"
          type="number"
          currentValue={s.resume_target_send_success_rate}
          onSave={(v) => patch.mutate({ resume_target_send_success_rate: Number(v) })}
          saving={saving}
        />
        <SettingInput
          label="PDF export success target (%)"
          type="number"
          currentValue={s.resume_target_export_success_rate}
          onSave={(v) => patch.mutate({ resume_target_export_success_rate: Number(v) })}
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

      <Section icon={Settings} title="Resume metrikalari (24 soat)">
        {resumeMetrics.isLoading ? (
          <p className="text-sm text-slate-500">Yuklanmoqda...</p>
        ) : resumeMetrics.data ? (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Builder ochilgan</p>
              <p className="mt-1 text-lg font-semibold text-slate-800">{resumeMetrics.data.opened_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Builder tayyor</p>
              <p className="mt-1 text-lg font-semibold text-slate-800">{resumeMetrics.data.ready_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Save success</p>
              <p className="mt-1 text-lg font-semibold text-emerald-700">{resumeMetrics.data.save_success_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Save error</p>
              <p className="mt-1 text-lg font-semibold text-red-600">{resumeMetrics.data.save_error_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Send success</p>
              <p className="mt-1 text-lg font-semibold text-emerald-700">{resumeMetrics.data.send_success_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Send error</p>
              <p className="mt-1 text-lg font-semibold text-red-600">{resumeMetrics.data.send_error_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Export success</p>
              <p className="mt-1 text-lg font-semibold text-emerald-700">{resumeMetrics.data.export_success_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Export error</p>
              <p className="mt-1 text-lg font-semibold text-red-600">{resumeMetrics.data.export_error_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Aktiv user</p>
              <p className="mt-1 text-lg font-semibold text-slate-800">{resumeMetrics.data.unique_users_24h}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">O'rtacha TTFI</p>
              <p className="mt-1 text-lg font-semibold text-slate-800">{resumeMetrics.data.avg_ttfi_ms} ms</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">O'rtacha save latency</p>
              <p className="mt-1 text-lg font-semibold text-slate-800">{resumeMetrics.data.avg_save_latency_ms} ms</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">O'rtacha send latency</p>
              <p className="mt-1 text-lg font-semibold text-slate-800">{resumeMetrics.data.avg_send_latency_ms} ms</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">O'rtacha export latency</p>
              <p className="mt-1 text-lg font-semibold text-slate-800">{resumeMetrics.data.avg_export_latency_ms} ms</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Metrikalar olinmadi.</p>
        )}
      </Section>

      <Section icon={Settings} title="Resume funnel (drop-off)">
        {resumeFunnel.isLoading ? (
          <p className="text-sm text-slate-500">Yuklanmoqda...</p>
        ) : resumeFunnel.data ? (
          <div className="space-y-2">
            {resumeFunnel.data.steps.map((item) => (
              <div key={item.step} className="rounded-xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-800">{item.step}</p>
                  <p className="text-xs text-slate-500">Completion: {item.completion_rate}%</p>
                </div>
                <div className="mt-1 grid grid-cols-3 gap-2 text-xs text-slate-600">
                  <p>Entered: {item.entered_users}</p>
                  <p>Completed: {item.completed_users}</p>
                  <p>Drop-off: {item.dropoff_users}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Funnel ma'lumotlari olinmadi.</p>
        )}
      </Section>

      <Section icon={Users} title="Resume user inspect">
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <input
            type="number"
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            placeholder="Telegram user ID"
            value={inspectUserId}
            onChange={(e) => {
              setInspectUserId(e.target.value);
              setInspectError("");
            }}
          />
          <button
            className="tap-target rounded-2xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            disabled={!inspectUserId || inspectResumeUser.isPending}
            onClick={() => inspectResumeUser.mutate(Number(inspectUserId))}
          >
            {inspectResumeUser.isPending ? "Qidirilmoqda..." : "Ko'rish"}
          </button>
        </div>
        {inspectError && <p className="text-xs text-red-600">{inspectError}</p>}
        {inspectResult && (
          <div className="space-y-2 rounded-xl border border-slate-200 p-3 text-sm">
            <p><strong>User:</strong> {inspectResult.user_id} {inspectResult.first_name ? `(${inspectResult.first_name})` : ""}</p>
            <p><strong>Username:</strong> {inspectResult.username || "-"}</p>
            <p><strong>Resume:</strong> {inspectResult.has_resume ? "Bor" : "Yo'q"}</p>
            <p><strong>Template:</strong> {inspectResult.selected_template}</p>
            <div className="rounded-lg bg-slate-50 p-2 text-xs text-slate-600">
              {Object.entries(inspectResult.profile_preview || {}).map(([key, val]) => (
                <p key={key}>{key}: {String(val)}</p>
              ))}
            </div>
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-700">Oxirgi eventlar</p>
              {inspectResult.recent_events.length === 0 ? (
                <p className="text-xs text-slate-500">Event yo'q</p>
              ) : (
                inspectResult.recent_events.slice(0, 8).map((ev, idx) => (
                  <p key={`${ev.event_name}-${idx}`} className="text-xs text-slate-600">
                    {ev.event_name} {ev.step ? `(${ev.step})` : ""} - {new Date(ev.created_at * 1000).toLocaleString()}
                  </p>
                ))
              )}
            </div>
          </div>
        )}
      </Section>

      <Section icon={Settings} title="Resume error diagnostics">
        {resumeDiagnostics.isLoading ? (
          <p className="text-sm text-slate-500">Yuklanmoqda...</p>
        ) : resumeDiagnostics.data ? (
          <div className="space-y-2">
            {resumeDiagnostics.data.items.length === 0 ? (
              <p className="text-sm text-emerald-700">Oxirgi 24 soatda xatolik topilmadi.</p>
            ) : (
              resumeDiagnostics.data.items.map((item, idx) => (
                <div key={`${item.source}-${item.error_text}-${idx}`} className="rounded-xl border border-slate-200 p-3">
                  <p className="text-sm font-semibold text-slate-800">{item.source} / {item.status}</p>
                  <p className="text-xs text-slate-600">{item.error_text}</p>
                  <p className="mt-1 text-xs text-slate-500">Count: {item.count_24h} | Last: {new Date(item.last_seen_at * 1000).toLocaleString()}</p>
                </div>
              ))
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Diagnostika ma'lumotlari olinmadi.</p>
        )}
      </Section>

      <Section icon={Settings} title="Resume KPI targets">
        {resumeGoals.isLoading ? (
          <p className="text-sm text-slate-500">Yuklanmoqda...</p>
        ) : resumeGoals.data ? (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            <div className={`rounded-xl border p-3 ${resumeGoals.data.creation_time_ok ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50"}`}>
              <p className="text-xs text-slate-600">Median creation time</p>
              <p className="text-sm font-semibold text-slate-800">{resumeGoals.data.median_creation_minutes} min</p>
              <p className="text-xs text-slate-500">Target: ≤ {resumeGoals.data.creation_time_target_minutes} min</p>
            </div>
            <div className={`rounded-xl border p-3 ${resumeGoals.data.completion_rate_ok ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50"}`}>
              <p className="text-xs text-slate-600">Wizard completion</p>
              <p className="text-sm font-semibold text-slate-800">{resumeGoals.data.completion_rate}%</p>
              <p className="text-xs text-slate-500">Target: ≥ {resumeGoals.data.completion_rate_target}%</p>
            </div>
            <div className={`rounded-xl border p-3 ${resumeGoals.data.send_success_rate_ok ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50"}`}>
              <p className="text-xs text-slate-600">Telegram send success</p>
              <p className="text-sm font-semibold text-slate-800">{resumeGoals.data.send_success_rate}%</p>
              <p className="text-xs text-slate-500">Target: ≥ {resumeGoals.data.send_success_rate_target}%</p>
            </div>
            <div className={`rounded-xl border p-3 ${resumeGoals.data.pdf_export_success_rate_ok ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50"}`}>
              <p className="text-xs text-slate-600">PDF export success</p>
              <p className="text-sm font-semibold text-slate-800">{resumeGoals.data.pdf_export_success_rate}%</p>
              <p className="text-xs text-slate-500">Target: ≥ {resumeGoals.data.pdf_export_success_rate_target}%</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3 md:col-span-2">
              <p className="text-xs text-slate-500">Window: {resumeGoals.data.window_hours} soat</p>
              <p className="text-xs text-slate-500">Opened users: {resumeGoals.data.opened_users} | Completed users: {resumeGoals.data.completed_users}</p>
              <p className="text-xs text-slate-500">Send attempts: {resumeGoals.data.send_attempts} | PDF export attempts: {resumeGoals.data.pdf_export_attempts}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">KPI ma'lumotlari olinmadi.</p>
        )}
      </Section>

      {saving && <p className="text-center text-xs text-slate-400">Saqlanmoqda...</p>}
    </div>
  );
}

