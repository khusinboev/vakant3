import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, FileText, Palette, Plus, Send, Trash2 } from "lucide-react";
import type { AxiosError } from "axios";

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

type ResumeTemplateItem = {
  id: string;
  title: string;
  description: string;
  supports_color: boolean;
  preview_variant: "single" | "split" | "mono";
  palette: string[];
};

type ResumeProfileResponse = {
  profile: ResumeProfileData;
  selected_template: string;
  accent_color: string;
  updated_at: number | null;
};

const EMPTY_PROFILE: ResumeProfileData = {
  full_name: "",
  position: "",
  phone: "",
  email: "",
  location: "",
  website: "",
  summary: "",
  experiences: [
    { role: "", company: "", start_date: "", end_date: "", location: "", description: "" },
  ],
  educations: [
    { school: "", degree: "", start_date: "", end_date: "", description: "" },
  ],
  skills: [],
  languages: [],
};

const LOCAL_TEMPLATES: ResumeTemplateItem[] = [
  {
    id: "clean",
    title: "Clean Classic",
    description: "Klassik, ATS-friendly, universal format.",
    supports_color: true,
    preview_variant: "single",
    palette: ["#0f766e", "#2563eb", "#b45309", "#be123c", "#374151"],
  },
  {
    id: "modern",
    title: "Modern Accent",
    description: "Zamonaviy blokli, headline urg'uli format.",
    supports_color: true,
    preview_variant: "split",
    palette: ["#2563eb", "#7c3aed", "#0f766e", "#ea580c", "#334155"],
  },
  {
    id: "compact",
    title: "Compact One-Page",
    description: "Bir sahifalik ixcham va monochrome ko'rinish.",
    supports_color: false,
    preview_variant: "mono",
    palette: ["#111827"],
  },
];

const STEPS = ["Asosiy", "Tajriba", "Ta'lim", "Ko'nikmalar", "Shablon"];
const RESUME_DRAFT_KEY = "resume_draft_v1";

function splitItems(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function saveLocalDraft(profile: ResumeProfileData, selectedTemplate: string, accentColor: string): void {
  const payload = {
    profile,
    selected_template: selectedTemplate,
    accent_color: accentColor,
    updated_at: Date.now(),
  };
  localStorage.setItem(RESUME_DRAFT_KEY, JSON.stringify(payload));
}

function loadLocalDraft(): ResumeProfileResponse | null {
  try {
    const raw = localStorage.getItem(RESUME_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ResumeProfileResponse>;
    return {
      profile: normalizeProfile(parsed.profile),
      selected_template: String(parsed.selected_template || "clean"),
      accent_color: String(parsed.accent_color || "#0f766e"),
      updated_at: Number(parsed.updated_at || Date.now()),
    };
  } catch {
    return null;
  }
}

function normalizeProfile(input: Partial<ResumeProfileData> | null | undefined): ResumeProfileData {
  const experiences = Array.isArray(input?.experiences) ? input.experiences : [];
  const educations = Array.isArray(input?.educations) ? input.educations : [];

  return {
    full_name: String(input?.full_name || ""),
    position: String(input?.position || ""),
    phone: String(input?.phone || ""),
    email: String(input?.email || ""),
    location: String(input?.location || ""),
    website: String(input?.website || ""),
    summary: String(input?.summary || ""),
    experiences:
      experiences.length > 0
        ? experiences.map((x) => ({
            role: String(x.role || ""),
            company: String(x.company || ""),
            start_date: String(x.start_date || ""),
            end_date: String(x.end_date || ""),
            location: String(x.location || ""),
            description: String(x.description || ""),
          }))
        : EMPTY_PROFILE.experiences,
    educations:
      educations.length > 0
        ? educations.map((x) => ({
            school: String(x.school || ""),
            degree: String(x.degree || ""),
            start_date: String(x.start_date || ""),
            end_date: String(x.end_date || ""),
            description: String(x.description || ""),
          }))
        : EMPTY_PROFILE.educations,
    skills: Array.isArray(input?.skills) ? input.skills.map((x) => String(x || "")).filter(Boolean) : [],
    languages: Array.isArray(input?.languages) ? input.languages.map((x) => String(x || "")).filter(Boolean) : [],
  };
}

function TemplatePreview({ variant, color }: { variant: "single" | "split" | "mono"; color: string }) {
  if (variant === "split") {
    return (
      <div className="h-24 w-full overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="flex h-full">
          <div className="w-1/3" style={{ backgroundColor: color }} />
          <div className="flex-1 p-2">
            <div className="h-2 w-2/3 rounded bg-slate-300" />
            <div className="mt-2 h-1.5 w-full rounded bg-slate-200" />
            <div className="mt-1 h-1.5 w-5/6 rounded bg-slate-200" />
            <div className="mt-2 h-1.5 w-2/3 rounded" style={{ backgroundColor: `${color}66` }} />
          </div>
        </div>
      </div>
    );
  }

  if (variant === "mono") {
    return (
      <div className="h-24 w-full overflow-hidden rounded-lg border border-slate-200 bg-white p-2">
        <div className="h-2 w-2/3 rounded bg-slate-800" />
        <div className="mt-2 h-1.5 w-full rounded bg-slate-300" />
        <div className="mt-1 h-1.5 w-4/5 rounded bg-slate-300" />
        <div className="mt-2 h-6 rounded bg-slate-100" />
      </div>
    );
  }

  return (
    <div className="h-24 w-full overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="h-5" style={{ backgroundColor: color }} />
      <div className="p-2">
        <div className="h-2 w-1/2 rounded bg-slate-300" />
        <div className="mt-2 h-1.5 w-full rounded bg-slate-200" />
        <div className="mt-1 h-1.5 w-5/6 rounded bg-slate-200" />
        <div className="mt-2 grid grid-cols-2 gap-1">
          <div className="h-4 rounded" style={{ backgroundColor: `${color}33` }} />
          <div className="h-4 rounded bg-slate-100" />
        </div>
      </div>
    </div>
  );
}

export default function ResumeStudioPage() {
  const queryClient = useQueryClient();
  const hydratedRef = useRef(false);

  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<ResumeProfileData>(EMPTY_PROFILE);
  const [selectedTemplate, setSelectedTemplate] = useState("clean");
  const [accentColor, setAccentColor] = useState("#0f766e");
  const [info, setInfo] = useState("");

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

  const templates = templatesQuery.data?.length ? templatesQuery.data : LOCAL_TEMPLATES;
  const activeTemplate = templates.find((x) => x.id === selectedTemplate) || templates[0];

  useEffect(() => {
    if (profileQuery.data && !hydratedRef.current) {
      setProfile(normalizeProfile(profileQuery.data.profile));
      setSelectedTemplate(profileQuery.data.selected_template || "clean");
      setAccentColor(profileQuery.data.accent_color || "#0f766e");
      hydratedRef.current = true;
    }
  }, [profileQuery.data]);

  useEffect(() => {
    if (!profileQuery.isError || hydratedRef.current) return;
    const localDraft = loadLocalDraft();
    if (!localDraft) return;
    setProfile(normalizeProfile(localDraft.profile));
    setSelectedTemplate(localDraft.selected_template || "clean");
    setAccentColor(localDraft.accent_color || "#0f766e");
    setInfo("Serverga ulanmagani uchun oxirgi lokal draft yuklandi.");
    hydratedRef.current = true;
  }, [profileQuery.isError]);

  useEffect(() => {
    if (!activeTemplate) return;
    if (!activeTemplate.supports_color) {
      setAccentColor(activeTemplate.palette[0] || "#111827");
      return;
    }
    const palette = activeTemplate.palette || [];
    if (palette.length > 0 && !palette.includes(accentColor)) {
      setAccentColor(palette[0]);
    }
  }, [activeTemplate, accentColor]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        profile,
        selected_template: selectedTemplate,
        accent_color: accentColor,
      };
      try {
        const { data } = await client.put<ResumeProfileResponse>("/resume/profile", payload);
        saveLocalDraft(data.profile, data.selected_template, data.accent_color);
        return { data, localFallback: false };
      } catch (error: unknown) {
        const axiosError = error as AxiosError<{ detail?: string }>;
        if (axiosError.response?.status === 401) {
          saveLocalDraft(profile, selectedTemplate, accentColor);
          return {
            data: {
              profile,
              selected_template: selectedTemplate,
              accent_color: accentColor,
              updated_at: Date.now(),
            } as ResumeProfileResponse,
            localFallback: true,
          };
        }
        throw error;
      }
    },
    onSuccess: (result) => {
      setInfo(
        result.localFallback
          ? "Internet/auth vaqtincha yo'q. Ma'lumotlar telefonda draft sifatida saqlandi."
          : "Resume ma'lumotlari saqlandi.",
      );
      queryClient.setQueryData(["resume", "profile"], result.data);
    },
  });

  const sendMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        profile,
        selected_template: selectedTemplate,
        accent_color: accentColor,
      };
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

  const updateExperience = (idx: number, key: keyof ResumeExperienceItem, value: string) => {
    setProfile((prev) => {
      const next = [...prev.experiences];
      next[idx] = { ...next[idx], [key]: value };
      return { ...prev, experiences: next };
    });
  };

  const updateEducation = (idx: number, key: keyof ResumeEducationItem, value: string) => {
    setProfile((prev) => {
      const next = [...prev.educations];
      next[idx] = { ...next[idx], [key]: value };
      return { ...prev, educations: next };
    });
  };

  if (profileQuery.isLoading) {
    return <div className="card p-4 text-sm text-slate-500">Yuklanmoqda...</div>;
  }

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-brand-600" />
          <h2 className="text-sm font-semibold text-slate-800">Resume Studio</h2>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Resume.io va Zety’dagi professional oqimga o'xshash tarzda: avval ma'lumotlar, keyin shablon va rang, oxirida Telegramga yuborish.
        </p>

        <div className="mt-3 grid grid-cols-5 gap-1 rounded-xl bg-slate-50 p-1">
          {STEPS.map((item, idx) => (
            <button
              key={item}
              className={`tap-target rounded-lg px-2 py-2 text-[11px] font-medium ${
                step === idx ? "bg-white text-slate-900" : "text-slate-500"
              }`}
              onClick={() => setStep(idx)}
            >
              {item}
            </button>
          ))}
        </div>
      </section>

      {step === 0 && (
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
          <textarea className="min-h-[110px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Professional summary" value={profile.summary} onChange={(e) => setProfile((p) => ({ ...p, summary: e.target.value }))} />
        </section>
      )}

      {step === 1 && (
        <section className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">Ish tajribasi</h3>
            <button
              className="tap-target rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700"
              onClick={() =>
                setProfile((p) => ({
                  ...p,
                  experiences: [...p.experiences, { role: "", company: "", start_date: "", end_date: "", location: "", description: "" }],
                }))
              }
            >
              <Plus size={13} className="inline mr-1" />Qo'shish
            </button>
          </div>

          {profile.experiences.map((exp, idx) => (
            <div key={idx} className="rounded-xl border border-slate-200 p-3 space-y-2">
              <div className="grid gap-2 md:grid-cols-2">
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Lavozim" value={exp.role} onChange={(e) => updateExperience(idx, "role", e.target.value)} />
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Kompaniya" value={exp.company} onChange={(e) => updateExperience(idx, "company", e.target.value)} />
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Boshlanish (MM/YYYY)" value={exp.start_date} onChange={(e) => updateExperience(idx, "start_date", e.target.value)} />
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Tugash (MM/YYYY yoki Hozir)" value={exp.end_date} onChange={(e) => updateExperience(idx, "end_date", e.target.value)} />
              </div>
              <input className="tap-target w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Joylashuv" value={exp.location} onChange={(e) => updateExperience(idx, "location", e.target.value)} />
              <textarea className="min-h-[84px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Yutuqlar va vazifalar (3-5 punkt)" value={exp.description} onChange={(e) => updateExperience(idx, "description", e.target.value)} />
              {profile.experiences.length > 1 && (
                <button
                  className="tap-target rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600"
                  onClick={() =>
                    setProfile((p) => ({ ...p, experiences: p.experiences.filter((_, i) => i !== idx) }))
                  }
                >
                  <Trash2 size={13} className="inline mr-1" />O'chirish
                </button>
              )}
            </div>
          ))}
        </section>
      )}

      {step === 2 && (
        <section className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">Ta'lim</h3>
            <button
              className="tap-target rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700"
              onClick={() =>
                setProfile((p) => ({
                  ...p,
                  educations: [...p.educations, { school: "", degree: "", start_date: "", end_date: "", description: "" }],
                }))
              }
            >
              <Plus size={13} className="inline mr-1" />Qo'shish
            </button>
          </div>

          {profile.educations.map((edu, idx) => (
            <div key={idx} className="rounded-xl border border-slate-200 p-3 space-y-2">
              <div className="grid gap-2 md:grid-cols-2">
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="O'quv yurti" value={edu.school} onChange={(e) => updateEducation(idx, "school", e.target.value)} />
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Daraja / Yo'nalish" value={edu.degree} onChange={(e) => updateEducation(idx, "degree", e.target.value)} />
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Boshlanish" value={edu.start_date} onChange={(e) => updateEducation(idx, "start_date", e.target.value)} />
                <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Tugash" value={edu.end_date} onChange={(e) => updateEducation(idx, "end_date", e.target.value)} />
              </div>
              <textarea className="min-h-[84px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Qo'shimcha ma'lumot" value={edu.description} onChange={(e) => updateEducation(idx, "description", e.target.value)} />
              {profile.educations.length > 1 && (
                <button
                  className="tap-target rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600"
                  onClick={() =>
                    setProfile((p) => ({ ...p, educations: p.educations.filter((_, i) => i !== idx) }))
                  }
                >
                  <Trash2 size={13} className="inline mr-1" />O'chirish
                </button>
              )}
            </div>
          ))}
        </section>
      )}

      {step === 3 && (
        <section className="card p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-800">Ko'nikmalar va tillar</h3>
          <input
            className="tap-target w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            placeholder="Ko'nikmalar (vergul bilan): Excel, CRM, Negotiation"
            value={profile.skills.join(", ")}
            onChange={(e) => setProfile((p) => ({ ...p, skills: splitItems(e.target.value) }))}
          />
          <input
            className="tap-target w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            placeholder="Tillar (vergul bilan): O'zbek, Rus, Ingliz"
            value={profile.languages.join(", ")}
            onChange={(e) => setProfile((p) => ({ ...p, languages: splitItems(e.target.value) }))}
          />
          <p className="text-xs text-slate-500">Pro builderlardagi kabi qisqa, aniq va ishga mos skill yozish tavsiya etiladi.</p>
        </section>
      )}

      {step === 4 && (
        <section className="card p-4 space-y-4">
          <h3 className="text-sm font-semibold text-slate-800">Shablon va rang tanlash</h3>

          <div className="grid gap-3 md:grid-cols-3">
            {templates.map((tpl) => {
              const selected = tpl.id === selectedTemplate;
              const previewColor = tpl.supports_color ? accentColor : tpl.palette[0] || "#111827";
              return (
                <button
                  key={tpl.id}
                  className={`tap-target rounded-xl border p-2 text-left ${selected ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white"}`}
                  onClick={() => setSelectedTemplate(tpl.id)}
                >
                  <TemplatePreview variant={tpl.preview_variant} color={previewColor} />
                  <p className="mt-2 text-sm font-semibold text-slate-800">{tpl.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{tpl.description}</p>
                  {selected && <p className="mt-1 text-[11px] font-semibold text-brand-700">Tanlangan</p>}
                </button>
              );
            })}
          </div>

          <div className="rounded-xl border border-slate-200 p-3">
            <div className="mb-2 flex items-center gap-2">
              <Palette size={14} className="text-slate-600" />
              <p className="text-sm font-semibold text-slate-700">Rang</p>
            </div>

            {activeTemplate?.supports_color ? (
              <div className="flex flex-wrap gap-2">
                {(activeTemplate.palette || []).map((color) => {
                  const active = accentColor === color;
                  return (
                    <button
                      key={color}
                      className={`tap-target h-8 w-8 rounded-full border-2 ${active ? "border-slate-900" : "border-white"}`}
                      style={{ backgroundColor: color }}
                      onClick={() => setAccentColor(color)}
                      aria-label={`Color ${color}`}
                    >
                      {active && <Check size={14} className="mx-auto text-white" />}
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-slate-500">Bu shablon monochrome. Rang o'zgartirish yo'q.</p>
            )}
          </div>
        </section>
      )}

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

        {(info || saveMutation.isError || sendMutation.isError) && (
          <p className={`mt-3 text-sm ${saveMutation.isError || sendMutation.isError ? "text-red-600" : "text-emerald-700"}`}>
            {saveMutation.isError || sendMutation.isError
              ? "Amaliyotda xatolik bo'ldi. Qayta urinib ko'ring."
              : info}
          </p>
        )}
      </section>
    </div>
  );
}
