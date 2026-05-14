import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import client from "../api/client";

type AdminState = {
  is_admin: boolean;
  auto_post_enabled: boolean;
  auto_post_channel: string;
  auto_post_min_salary: number;
  referral_enabled: boolean;
  referral_required_count: number;
};

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

  const s = local || state.data;

  if (state.isLoading && !s) return <div className="card p-4 text-sm">Yuklanmoqda...</div>;
  if (state.isError || !s) {
    return <div className="card p-4 text-sm text-red-600">Admin panel faqat adminlar uchun.</div>;
  }

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Auto-post sozlamalari</h3>
        <div className="mt-3 space-y-3 text-sm">
          <label className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span>Faol</span>
            <input
              type="checkbox"
              checked={s.auto_post_enabled}
              onChange={(e) => patch.mutate({ auto_post_enabled: e.target.checked })}
            />
          </label>

          <label className="block rounded-xl bg-slate-50 px-3 py-2">
            <p className="text-slate-500">Kanal (@username yoki -100...)</p>
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              value={s.auto_post_channel}
              onChange={(e) => setLocal({ ...s, auto_post_channel: e.target.value })}
              onBlur={() => patch.mutate({ auto_post_channel: s.auto_post_channel })}
            />
          </label>

          <label className="block rounded-xl bg-slate-50 px-3 py-2">
            <p className="text-slate-500">Minimal maosh (so'm)</p>
            <input
              type="number"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              value={s.auto_post_min_salary}
              onChange={(e) => setLocal({ ...s, auto_post_min_salary: Number(e.target.value || 0) })}
              onBlur={() => patch.mutate({ auto_post_min_salary: s.auto_post_min_salary })}
            />
          </label>
        </div>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Referral gate</h3>
        <div className="mt-3 space-y-3 text-sm">
          <label className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span>Faol</span>
            <input
              type="checkbox"
              checked={s.referral_enabled}
              onChange={(e) => patch.mutate({ referral_enabled: e.target.checked })}
            />
          </label>

          <label className="block rounded-xl bg-slate-50 px-3 py-2">
            <p className="text-slate-500">Talab qilinadigan referral soni</p>
            <input
              type="number"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              value={s.referral_required_count}
              onChange={(e) => setLocal({ ...s, referral_required_count: Number(e.target.value || 0) })}
              onBlur={() => patch.mutate({ referral_required_count: s.referral_required_count })}
            />
          </label>
        </div>
      </section>

      {patch.isPending && <div className="text-xs text-slate-500">Saqlanmoqda...</div>}
    </div>
  );
}
