import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Send } from "lucide-react";

import client from "../api/client";

type ResumeExperienceItem = {
  role: string;
  company: string;
  start_date: string;
  end_date: string;
  location: string;
  description: string;
};

type ResumeEducationItem = {
  school: string;
  degree: string;
  start_date: string;
  end_date: string;
  description: string;
};

type ResumeProfileData = {
  full_name: string;
  position: string;
  phone: string;
  email: string;
  location: string;
  website: string;
  summary: string;
  experiences: ResumeExperienceItem[];
  educations: ResumeEducationItem[];
  skills: string[];
  languages: string[];
};

type ResumeProfileResponse = {
  profile: ResumeProfileData;
  selected_template: string;
  accent_color: string;
  updated_at: number | null;
};

type ResumeEventPayload = {
  event_name: string;
  step?: string;
  meta_json?: string;
};

const EMPTY_PROFILE: ResumeProfileData = {
  full_name: "",
  position: "",
  phone: "",
  email: "",
  location: "",
  website: "",
  summary: "",
  experiences: [],
  educations: [],
  skills: [],
  languages: [],
};

function splitItems(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeProfile(input: Partial<ResumeProfileData> | null | undefined): ResumeProfileData {
  return {
    full_name: String(input?.full_name || ""),
    position: String(input?.position || ""),
    phone: String(input?.phone || ""),
    email: String(input?.email || ""),
    location: String(input?.location || ""),
    website: String(input?.website || ""),
    summary: String(input?.summary || ""),
    experiences: Array.isArray(input?.experiences)
      ? input.experiences.map((x) => ({
          role: String(x.role || ""),
          company: String(x.company || ""),
          start_date: String(x.start_date || ""),
          end_date: String(x.end_date || ""),
          location: String(x.location || ""),
          description: String(x.description || ""),
        }))
      : [],
    educations: Array.isArray(input?.educations)
      ? input.educations.map((x) => ({
          school: String(x.school || ""),
          degree: String(x.degree || ""),
          start_date: String(x.start_date || ""),
          end_date: String(x.end_date || ""),
          description: String(x.description || ""),
        }))
      : [],
    skills: Array.isArray(input?.skills) ? input.skills.map((x) => String(x || "")).filter(Boolean) : [],
    languages: Array.isArray(input?.languages)
      ? input.languages.map((x) => String(x || "")).filter(Boolean)
      : [],
  };
}

export default function ResumeStudioPage() {
  const queryClient = useQueryClient();
  const openedTrackedRef = useRef(false);

  const [profile, setProfile] = useState<ResumeProfileData>(EMPTY_PROFILE);
  const [experienceText, setExperienceText] = useState("");
  const [educationText, setEducationText] = useState("");
  const [info, setInfo] = useState("");

  const trackEvent = (payload: ResumeEventPayload) => {
    void client.post("/resume/events", payload).catch(() => undefined);
  };

  useEffect(() => {
    const onFocusIn = (event: FocusEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const tag = target.tagName.toLowerCase();
      const isEditable = tag === "input" || tag === "textarea" || tag === "select";
      if (!isEditable) return;

      setTimeout(() => target.scrollIntoView({ block: "center", behavior: "smooth" }), 80);
      setTimeout(() => target.scrollIntoView({ block: "center", behavior: "smooth" }), 260);
    };

    document.addEventListener("focusin", onFocusIn);
    return () => document.removeEventListener("focusin", onFocusIn);
  }, []);

  const profileQuery = useQuery({
    queryKey: ["resume", "profile"],
    queryFn: async () => {
      const { data } = await client.get<ResumeProfileResponse>("/resume/profile");
      return data;
    },
  });

  useEffect(() => {
    if (!profileQuery.data) return;

    const normalized = normalizeProfile(profileQuery.data.profile);
    setProfile(normalized);
    setExperienceText(normalized.experiences.map((x) => x.description).filter(Boolean).join("\n\n"));
    setEducationText(normalized.educations.map((x) => x.description).filter(Boolean).join("\n\n"));
    if (!openedTrackedRef.current) {
      trackEvent({ event_name: "builder_opened", step: "basic" });
      openedTrackedRef.current = true;
    }
  }, [profileQuery.data]);

  const buildPayload = () => ({
    profile: {
      ...profile,
      experiences: experienceText.trim()
        ? [
            {
              role: "",
              company: "",
              start_date: "",
              end_date: "",
              location: "",
              description: experienceText.trim(),
            },
          ]
        : [],
      educations: educationText.trim()
        ? [
            {
              school: "",
              degree: "",
              start_date: "",
              end_date: "",
              description: educationText.trim(),
            },
          ]
        : [],
      skills: profile.skills,
      languages: profile.languages,
    },
    selected_template: "clean",
    accent_color: "#0f766e",
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const { data } = await client.put<ResumeProfileResponse>("/resume/profile", buildPayload());
      return data;
    },
    onSuccess: (data) => {
      setInfo("Ma'lumotlar saqlandi.");
      queryClient.setQueryData(["resume", "profile"], data);
      trackEvent({ event_name: "save_success", step: "basic" });
    },
    onError: () => {
      setInfo("Saqlashda xatolik bo'ldi.");
      trackEvent({ event_name: "save_error", step: "basic" });
    },
  });

  const sendMutation = useMutation({
    mutationFn: async () => {
      await client.put<ResumeProfileResponse>("/resume/profile", buildPayload());
      const { data } = await client.post<{ ok: boolean; message: string }>("/resume/send-telegram", {
        template_id: "clean",
      });
      return data;
    },
    onSuccess: (data) => {
      setInfo(data.message || "Resume Telegramga yuborildi.");
      queryClient.invalidateQueries({ queryKey: ["resume", "profile"] });
      trackEvent({ event_name: "send_success", step: "final" });
    },
    onError: () => {
      setInfo("Yuborishda xatolik bo'ldi.");
      trackEvent({ event_name: "send_error", step: "final" });
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
          <FileText size={16} className="text-brand-600" />
          <h2 className="text-sm font-semibold text-slate-800">Resume bo'limi</h2>
        </div>
        <p className="mt-2 text-sm text-slate-600">Quyidagi maydonlarni to'ldirib saqlang yoki Telegramga yuboring.</p>
      </section>

      <section className="card p-4 space-y-3">
        <h3 className="text-sm font-semibold text-slate-800">Asosiy ma'lumotlar</h3>
        <div className="grid gap-3 md:grid-cols-2">
          <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="F.I.Sh" value={profile.full_name} onChange={(e) => setProfile((p) => ({ ...p, full_name: e.target.value }))} />
          <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Lavozim" value={profile.position} onChange={(e) => setProfile((p) => ({ ...p, position: e.target.value }))} />
          <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Telefon" value={profile.phone} onChange={(e) => setProfile((p) => ({ ...p, phone: e.target.value }))} />
          <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Email" value={profile.email} onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))} />
          <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Manzil" value={profile.location} onChange={(e) => setProfile((p) => ({ ...p, location: e.target.value }))} />
          <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Portfolio / LinkedIn" value={profile.website} onChange={(e) => setProfile((p) => ({ ...p, website: e.target.value }))} />
        </div>
        <textarea className="min-h-[110px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Qisqacha o'zingiz haqingizda" value={profile.summary} onChange={(e) => setProfile((p) => ({ ...p, summary: e.target.value }))} />
      </section>

      <section className="card p-4 space-y-3">
        <h3 className="text-sm font-semibold text-slate-800">Tajriba va ta'lim</h3>
        <textarea
          className="min-h-[110px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          placeholder="Ish tajribangizni yozing"
          value={experienceText}
          onChange={(e) => setExperienceText(e.target.value)}
        />
        <textarea
          className="min-h-[110px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          placeholder="Ta'lim ma'lumotingizni yozing"
          value={educationText}
          onChange={(e) => setEducationText(e.target.value)}
        />
      </section>

      <section className="card p-4 space-y-3">
        <h3 className="text-sm font-semibold text-slate-800">Ko'nikmalar va tillar</h3>
        <input
          className="tap-target w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          placeholder="Ko'nikmalar (vergul bilan)"
          value={profile.skills.join(", ")}
          onChange={(e) => setProfile((p) => ({ ...p, skills: splitItems(e.target.value) }))}
        />
        <input
          className="tap-target w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          placeholder="Tillar (vergul bilan)"
          value={profile.languages.join(", ")}
          onChange={(e) => setProfile((p) => ({ ...p, languages: splitItems(e.target.value) }))}
        />
      </section>

      <section className="card p-4">
        <div className="grid gap-2 md:grid-cols-2">
          <button
            className="tap-target rounded-2xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700"
            disabled={isBusy}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? "Saqlanmoqda..." : "Saqlash"}
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

        {Boolean(info) && <p className="mt-3 text-sm text-slate-700">{info}</p>}
      </section>
    </div>
  );
}
