import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Send, Sparkles } from "lucide-react";

import client from "../api/client";

type ResumeProfileData = {
  full_name: string;
  position: string;
  phone: string;
  email: string;
  location: string;
  website: string;
  summary: string;
  experience: string;
  education: string;
  skills: string[];
  languages: string[];
};

type ResumeProfileResponse = {
  profile: ResumeProfileData;
  selected_template: string;
  updated_at: number | null;
};

type ResumeTemplateItem = {
  id: string;
  title: string;
  description: string;
};

const EMPTY_PROFILE: ResumeProfileData = {
  full_name: "",
  position: "",
  phone: "",
  email: "",
  location: "",
  website: "",
  summary: "",
  experience: "",
  education: "",
  skills: [],
  languages: [],
};

function splitItems(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function HubPage() {
  const queryClient = useQueryClient();
  const hydratedRef = useRef(false);

  const [profile, setProfile] = useState<ResumeProfileData>(EMPTY_PROFILE);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("clean");
  const [info, setInfo] = useState<string>("");

  const profileQuery = useQuery({
    queryKey: ["resume", "profile"],
    queryFn: async () => {
      const { data } = await client.get<ResumeProfileResponse>("/resume/profile");
      return data;
    },
  });

  const templatesQuery = useQuery({
    queryKey: ["resume", "templates"],
    queryFn: async () => {
      const { data } = await client.get<{ items: ResumeTemplateItem[] }>("/resume/templates");
      return data.items;
    },
  });

  useEffect(() => {
    if (profileQuery.data && !hydratedRef.current) {
      setProfile(profileQuery.data.profile);
      setSelectedTemplate(profileQuery.data.selected_template || "clean");
      hydratedRef.current = true;
    }
  }, [profileQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = { profile, selected_template: selectedTemplate };
      const { data } = await client.put<ResumeProfileResponse>("/resume/profile", payload);
      return data;
    },
    onSuccess: (data) => {
      setInfo("Ma'lumotlar saqlandi.");
      queryClient.setQueryData(["resume", "profile"], data);
    },
  });

  const sendMutation = useMutation({
    mutationFn: async () => {
      const payload = { profile, selected_template: selectedTemplate };
      await client.put<ResumeProfileResponse>("/resume/profile", payload);
      const { data } = await client.post<{ ok: boolean; message: string }>("/resume/send-telegram", {
        template_id: selectedTemplate,
      });
      return data;
    },
    onSuccess: (data) => {
      setInfo(data.message || "Resume Telegramga yuborildi.");
      queryClient.invalidateQueries({ queryKey: ["resume", "profile"] });
    },
  });

  const isBusy = saveMutation.isPending || sendMutation.isPending;

  if (profileQuery.isLoading) {
    return <div className="card p-4 text-sm text-slate-500">Yuklanmoqda...</div>;
  }

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-brand-600" />
          <h2 className="text-sm font-semibold text-slate-800">Markaz</h2>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Bu bo'limda resume va keyinchalik boshqa foydali vositalar bo'ladi.
        </p>
      </section>

      <section className="card p-4">
        <div className="mb-3 flex items-center gap-2">
          <FileText size={16} className="text-emerald-600" />
          <h3 className="text-sm font-semibold text-slate-800">Resume yasash</h3>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="F.I.Sh"
            value={profile.full_name}
            onChange={(e) => setProfile((prev) => ({ ...prev, full_name: e.target.value }))}
          />
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="Lavozim (masalan: Sotuv menejeri)"
            value={profile.position}
            onChange={(e) => setProfile((prev) => ({ ...prev, position: e.target.value }))}
          />
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="Telefon"
            value={profile.phone}
            onChange={(e) => setProfile((prev) => ({ ...prev, phone: e.target.value }))}
          />
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="Email"
            value={profile.email}
            onChange={(e) => setProfile((prev) => ({ ...prev, email: e.target.value }))}
          />
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="Manzil"
            value={profile.location}
            onChange={(e) => setProfile((prev) => ({ ...prev, location: e.target.value }))}
          />
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="LinkedIn/Portfolio havolasi"
            value={profile.website}
            onChange={(e) => setProfile((prev) => ({ ...prev, website: e.target.value }))}
          />
        </div>

        <textarea
          className="mt-3 min-h-[90px] w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
          placeholder="Qisqacha ma'lumot"
          value={profile.summary}
          onChange={(e) => setProfile((prev) => ({ ...prev, summary: e.target.value }))}
        />

        <textarea
          className="mt-3 min-h-[110px] w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
          placeholder="Ish tajribasi"
          value={profile.experience}
          onChange={(e) => setProfile((prev) => ({ ...prev, experience: e.target.value }))}
        />

        <textarea
          className="mt-3 min-h-[90px] w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
          placeholder="Ta'lim"
          value={profile.education}
          onChange={(e) => setProfile((prev) => ({ ...prev, education: e.target.value }))}
        />

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="Ko'nikmalar (vergul bilan)"
            value={profile.skills.join(", ")}
            onChange={(e) => setProfile((prev) => ({ ...prev, skills: splitItems(e.target.value) }))}
          />
          <input
            className="tap-target rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="Tillar (vergul bilan)"
            value={profile.languages.join(", ")}
            onChange={(e) => setProfile((prev) => ({ ...prev, languages: splitItems(e.target.value) }))}
          />
        </div>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Shablon tanlang</h3>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {(templatesQuery.data || []).map((tpl) => {
            const active = selectedTemplate === tpl.id;
            return (
              <button
                key={tpl.id}
                className={`tap-target rounded-xl border p-3 text-left ${
                  active ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white"
                }`}
                onClick={() => setSelectedTemplate(tpl.id)}
              >
                <p className="text-sm font-semibold text-slate-800">{tpl.title}</p>
                <p className="mt-1 text-xs text-slate-500">{tpl.description}</p>
              </button>
            );
          })}
        </div>

        <div className="mt-4 grid gap-2 md:grid-cols-2">
          <button
            className="tap-target rounded-2xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700"
            disabled={isBusy}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? "Saqlanmoqda..." : "Ma'lumotni saqlash"}
          </button>
          <button
            className="tap-target flex items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white"
            disabled={isBusy}
            onClick={() => sendMutation.mutate()}
          >
            <Send size={15} />
            {sendMutation.isPending ? "Yuborilmoqda..." : "Telegramga yuborish"}
          </button>
        </div>

        {(info || saveMutation.isError || sendMutation.isError) && (
          <p className={`mt-3 text-sm ${saveMutation.isError || sendMutation.isError ? "text-red-600" : "text-emerald-700"}`}>
            {saveMutation.isError || sendMutation.isError
              ? "Amaliyotda xatolik bo'ldi. Qayta urinib ko'ring."
              : info}
          </p>
        )}
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Yaqinda shu yerga qo'shiladi</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>Cover letter generator</li>
          <li>Interview savollariga tayyorgarlik</li>
          <li>Kasbiy profilingiz uchun tavsiyalar</li>
        </ul>
      </section>
    </div>
  );
}
