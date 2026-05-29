import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, FileText, Send } from "lucide-react";

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

type ResumeTemplateItem = {
  id: string;
  title: string;
  description: string;
  supports_color: boolean;
  preview_variant: "single" | "split" | "mono";
  palette: string[];
};

type ResumeEventPayload = {
  event_name: string;
  step?: string;
  meta_json?: string;
};

type StepId = "basic" | "experience" | "education" | "skills" | "summary" | "template";

type StepItem = {
  id: StepId;
  label: string;
};

type LocalDraft = {
  profile: ResumeProfileData;
  selected_template: string;
  accent_color: string;
  job_description: string;
  updated_at: number;
};

const LOCAL_DRAFT_KEY = "resume_wizard_draft_v2";
const STEP_ITEMS: StepItem[] = [
  { id: "basic", label: "Asosiy" },
  { id: "experience", label: "Tajriba" },
  { id: "education", label: "Ta'lim" },
  { id: "skills", label: "Ko'nikma" },
  { id: "summary", label: "Summary" },
  { id: "template", label: "Shablon" },
];

const LOCAL_TEMPLATES: ResumeTemplateItem[] = [
  {
    id: "clean",
    title: "Clean Classic",
    description: "Soddaroq klassik ko'rinish.",
    supports_color: true,
    preview_variant: "single",
    palette: ["#0f766e", "#2563eb", "#b45309", "#be123c", "#374151"],
  },
  {
    id: "modern",
    title: "Modern Accent",
    description: "Qisqa va zamonaviy blokli uslub.",
    supports_color: true,
    preview_variant: "split",
    palette: ["#2563eb", "#7c3aed", "#0f766e", "#ea580c", "#334155"],
  },
  {
    id: "compact",
    title: "Compact One-Page",
    description: "Bir sahifaga sig'adigan ixcham format.",
    supports_color: false,
    preview_variant: "mono",
    palette: ["#111827"],
  },
];

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

const EMPTY_EXPERIENCE: ResumeExperienceItem = {
  role: "",
  company: "",
  start_date: "",
  end_date: "",
  location: "",
  description: "",
};

const EMPTY_EDUCATION: ResumeEducationItem = {
  school: "",
  degree: "",
  start_date: "",
  end_date: "",
  description: "",
};

const STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "that",
  "this",
  "your",
  "you",
  "our",
  "will",
  "are",
  "or",
  "to",
  "in",
  "of",
  "on",
  "at",
  "by",
  "as",
  "an",
  "a",
]);

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timeout = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timeout);
  }, [value, delayMs]);

  return debounced;
}

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

function saveLocalDraft(draft: LocalDraft): void {
  localStorage.setItem(LOCAL_DRAFT_KEY, JSON.stringify(draft));
}

function loadLocalDraft(): LocalDraft | null {
  try {
    const raw = localStorage.getItem(LOCAL_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LocalDraft>;
    return {
      profile: normalizeProfile(parsed.profile),
      selected_template: String(parsed.selected_template || "clean"),
      accent_color: String(parsed.accent_color || "#0f766e"),
      job_description: String(parsed.job_description || ""),
      updated_at: Number(parsed.updated_at || Date.now()),
    };
  } catch {
    return null;
  }
}

function makeFingerprint(profile: ResumeProfileData, selectedTemplate: string, accentColor: string): string {
  return JSON.stringify({ profile, selectedTemplate, accentColor });
}

function extractTopKeywords(jobDescription: string): string[] {
  const words = (jobDescription.toLowerCase().match(/[a-zA-Z][a-zA-Z0-9+.#-]{2,}/g) || [])
    .filter((word) => !STOP_WORDS.has(word));
  const freq = new Map<string, number>();
  for (const word of words) {
    freq.set(word, (freq.get(word) || 0) + 1);
  }
  return [...freq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([word]) => word);
}

function getRoleBasedSuggestions(role: string): string[] {
  const lower = role.toLowerCase();
  if (lower.includes("engineer") || lower.includes("developer")) {
    return [
      "Optimized key flows and reduced response time by 30%.",
      "Implemented automated tests and reduced production bugs by 20%.",
      "Led cross-team delivery of a core feature used by daily active users.",
    ];
  }
  if (lower.includes("sales") || lower.includes("manager")) {
    return [
      "Exceeded quarterly targets by 18% through focused pipeline management.",
      "Built client relationships that improved retention by 15%.",
      "Mentored team members and improved close rate across the team.",
    ];
  }
  return [
    "Improved team workflows and delivered measurable business results.",
    "Collaborated with stakeholders to ship high-priority initiatives on time.",
    "Tracked KPIs and improved process quality with clear ownership.",
  ];
}

function TemplatePreview({ template, color }: { template: ResumeTemplateItem; color: string }) {
  if (template.preview_variant === "split") {
    return (
      <div className="h-20 w-full overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="flex h-full">
          <div className="w-1/3" style={{ backgroundColor: color }} />
          <div className="flex-1 p-2">
            <div className="h-2 w-2/3 rounded bg-slate-300" />
            <div className="mt-2 h-1.5 w-full rounded bg-slate-200" />
            <div className="mt-1 h-1.5 w-4/5 rounded bg-slate-200" />
          </div>
        </div>
      </div>
    );
  }

  if (template.preview_variant === "mono") {
    return (
      <div className="h-20 w-full overflow-hidden rounded-lg border border-slate-200 bg-white p-2">
        <div className="h-2 w-2/3 rounded bg-slate-800" />
        <div className="mt-2 h-1.5 w-full rounded bg-slate-300" />
        <div className="mt-1 h-1.5 w-4/5 rounded bg-slate-300" />
      </div>
    );
  }

  return (
    <div className="h-20 w-full overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="h-5" style={{ backgroundColor: color }} />
      <div className="p-2">
        <div className="h-2 w-1/2 rounded bg-slate-300" />
        <div className="mt-2 h-1.5 w-full rounded bg-slate-200" />
        <div className="mt-1 h-1.5 w-5/6 rounded bg-slate-200" />
      </div>
    </div>
  );
}

function ResumePreview({
  profile,
  accentColor,
  templateName,
}: {
  profile: ResumeProfileData;
  accentColor: string;
  templateName: string;
}) {
  return (
    <section className="card p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Live Preview</h3>
        <span className="text-[11px] text-slate-400">{templateName}</span>
      </div>
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="px-4 py-3 text-white" style={{ backgroundColor: accentColor }}>
          <p className="text-sm font-semibold">{profile.full_name || "Nomsiz nomzod"}</p>
          <p className="text-xs opacity-90">{profile.position || "Lavozim ko'rsatilmagan"}</p>
        </div>
        <div className="space-y-3 p-4 text-xs">
          <div>
            <p className="font-semibold text-slate-700">Kontakt</p>
            <p className="mt-1 text-slate-600">
              {[profile.phone, profile.email, profile.location].filter(Boolean).join(" | ") || "Kontakt kiritilmagan"}
            </p>
          </div>
          <div>
            <p className="font-semibold text-slate-700">Summary</p>
            <p className="mt-1 whitespace-pre-wrap text-slate-600">{profile.summary || "Summary kiritilmagan"}</p>
          </div>
          <div>
            <p className="font-semibold text-slate-700">Tajriba</p>
            {profile.experiences.length === 0 ? (
              <p className="mt-1 text-slate-500">Kiritilmagan</p>
            ) : (
              <ul className="mt-1 list-disc space-y-1 pl-4 text-slate-600">
                {profile.experiences.slice(0, 3).map((item, idx) => (
                  <li key={idx}>{[item.role, item.company].filter(Boolean).join(" - ") || "Tajriba"}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="font-semibold text-slate-700">Ko'nikmalar</p>
            <p className="mt-1 text-slate-600">{profile.skills.join(", ") || "Kiritilmagan"}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function ResumeStudioPage() {
  const queryClient = useQueryClient();
  const openedTrackedRef = useRef(false);
  const hydratedRef = useRef(false);
  const readyTrackedRef = useRef(false);
  const screenStartMsRef = useRef(typeof performance !== "undefined" ? performance.now() : Date.now());
  const saveStartMsRef = useRef<number | null>(null);
  const sendStartMsRef = useRef<number | null>(null);
  const syncFpRef = useRef<string>("");
  const serverUpdatedAtRef = useRef<number>(0);
  const localDirtyRef = useRef(false);
  const conflictRef = useRef(false);

  const [profile, setProfile] = useState<ResumeProfileData>(EMPTY_PROFILE);
  const [selectedTemplate, setSelectedTemplate] = useState("clean");
  const [accentColor, setAccentColor] = useState("#0f766e");
  const [step, setStep] = useState(0);
  const [jobDescription, setJobDescription] = useState("");
  const [info, setInfo] = useState("");
  const [localDirty, setLocalDirty] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "saving" | "synced" | "error">("idle");
  const [hasConflict, setHasConflict] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const trackEvent = (payload: ResumeEventPayload) => {
    void client.post("/resume/events", payload).catch(() => undefined);
  };

  const makeIdempotencyKey = (action: string): string => {
    const rand = Math.random().toString(36).slice(2, 10);
    return `${action}:${Date.now()}:${rand}`;
  };

  const authHintAvailable = Boolean(
    localStorage.getItem("session_token") || window.Telegram?.WebApp?.initData || window.Telegram?.WebApp?.initDataUnsafe?.user?.id,
  );

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
    retry: false,
    enabled: authHintAvailable,
    refetchInterval: 30000,
  });

  const templatesQuery = useQuery({
    queryKey: ["resume", "templates"],
    queryFn: async () => {
      const { data } = await client.get<{ items: ResumeTemplateItem[] }>("/resume/templates");
      return data.items;
    },
    retry: false,
    enabled: authHintAvailable,
  });

  const templates = templatesQuery.data?.length ? templatesQuery.data : LOCAL_TEMPLATES;
  const activeTemplate = templates.find((item) => item.id === selectedTemplate) || templates[0];

  const markDirty = () => {
    setLocalDirty(true);
    localDirtyRef.current = true;
  };

  const applyServerPayload = (server: ResumeProfileResponse) => {
    const normalized = normalizeProfile(server.profile);
    setProfile(normalized);
    setSelectedTemplate(server.selected_template || "clean");
    setAccentColor(server.accent_color || "#0f766e");
    serverUpdatedAtRef.current = Number(server.updated_at || 0);
    setLocalDirty(false);
    localDirtyRef.current = false;
    setHasConflict(false);
    conflictRef.current = false;
  };

  useEffect(() => {
    if (hydratedRef.current) return;
    const localDraft = loadLocalDraft();
    if (!localDraft) return;
    setProfile(normalizeProfile(localDraft.profile));
    setSelectedTemplate(localDraft.selected_template || "clean");
    setAccentColor(localDraft.accent_color || "#0f766e");
    setJobDescription(localDraft.job_description || "");
    setInfo("Lokal draft tiklandi.");
    hydratedRef.current = true;
    setLocalDirty(true);
    localDirtyRef.current = true;
  }, []);

  useEffect(() => {
    if (!profileQuery.data) return;

    if (!hydratedRef.current) {
      applyServerPayload(profileQuery.data);
      hydratedRef.current = true;

      const localDraft = loadLocalDraft();
      const localUpdatedAt = Number(localDraft?.updated_at || 0);
      const serverUpdatedAt = Number(profileQuery.data.updated_at || 0);
      if (localDraft && localUpdatedAt > serverUpdatedAt) {
        setProfile(normalizeProfile(localDraft.profile));
        setSelectedTemplate(localDraft.selected_template || "clean");
        setAccentColor(localDraft.accent_color || "#0f766e");
        setJobDescription(localDraft.job_description || "");
        setInfo("Lokal draft serverdan yangi, vaqtincha lokal holat ko'rsatildi.");
        setHasConflict(true);
        conflictRef.current = true;
        setLocalDirty(true);
        localDirtyRef.current = true;
      }
    } else {
      const remoteTs = Number(profileQuery.data.updated_at || 0);
      if (remoteTs > serverUpdatedAtRef.current && localDirtyRef.current) {
        setHasConflict(true);
        conflictRef.current = true;
      } else if (remoteTs > serverUpdatedAtRef.current && !localDirtyRef.current) {
        applyServerPayload(profileQuery.data);
      }
    }

    if (!openedTrackedRef.current) {
      trackEvent({ event_name: "builder_opened", step: "basic" });
      openedTrackedRef.current = true;
    }
    if (!readyTrackedRef.current) {
      const readyMs = Math.max(0, Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - screenStartMsRef.current));
      trackEvent({ event_name: "builder_ready", step: "basic", meta_json: JSON.stringify({ ttfi_ms: readyMs }) });
      readyTrackedRef.current = true;
    }
  }, [profileQuery.data]);

  useEffect(() => {
    if (!activeTemplate) return;
    if (!activeTemplate.supports_color) {
      setAccentColor(activeTemplate.palette[0] || "#111827");
      return;
    }
    if (activeTemplate.palette.length > 0 && !activeTemplate.palette.includes(accentColor)) {
      setAccentColor(activeTemplate.palette[0]);
    }
  }, [activeTemplate, accentColor]);

  useEffect(() => {
    if (!hydratedRef.current) return;
    const timeout = setTimeout(() => {
      saveLocalDraft({
        profile,
        selected_template: selectedTemplate,
        accent_color: accentColor,
        job_description: jobDescription,
        updated_at: Date.now(),
      });
    }, 900);
    return () => clearTimeout(timeout);
  }, [profile, selectedTemplate, accentColor, jobDescription]);

  const persistProfile = async (keyPrefix: string): Promise<ResumeProfileResponse> => {
    const payload = {
      profile,
      selected_template: selectedTemplate,
      accent_color: accentColor,
    };
    const fp = makeFingerprint(profile, selectedTemplate, accentColor);
    syncFpRef.current = fp;
    const { data } = await client.put<ResumeProfileResponse>("/resume/profile", payload, {
      headers: { "X-Idempotency-Key": makeIdempotencyKey(keyPrefix) },
    });
    return data;
  };

  const currentFingerprint = useMemo(
    () => makeFingerprint(profile, selectedTemplate, accentColor),
    [profile, selectedTemplate, accentColor],
  );

  useEffect(() => {
    if (!hydratedRef.current || !authHintAvailable) return;
    const interval = setInterval(() => {
      if (localDirtyRef.current && !saveMutation.isPending && !sendMutation.isPending && !autoSaveMutation.isPending) {
        autoSaveMutation.mutate();
      }
    }, 15000);
    return () => clearInterval(interval);
  }, [authHintAvailable]);

  const saveMutation = useMutation({
    retry: false,
    onMutate: () => {
      saveStartMsRef.current = typeof performance !== "undefined" ? performance.now() : Date.now();
    },
    mutationFn: async () => {
      return persistProfile("resume_save");
    },
    onSuccess: (data) => {
      setInfo("Ma'lumotlar saqlandi.");
      queryClient.setQueryData(["resume", "profile"], data);
      serverUpdatedAtRef.current = Number(data.updated_at || serverUpdatedAtRef.current);
      if (syncFpRef.current === currentFingerprint) {
        setLocalDirty(false);
        localDirtyRef.current = false;
      }
      setHasConflict(false);
      conflictRef.current = false;
      setSyncStatus("synced");
      const latencyMs = Math.max(
        0,
        Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - (saveStartMsRef.current ?? (typeof performance !== "undefined" ? performance.now() : Date.now()))),
      );
      trackEvent({ event_name: "save_success", step: "basic", meta_json: JSON.stringify({ latency_ms: latencyMs }) });
    },
    onError: () => {
      setInfo("Saqlashda xatolik bo'ldi.");
      setSyncStatus("error");
      const latencyMs = Math.max(
        0,
        Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - (saveStartMsRef.current ?? (typeof performance !== "undefined" ? performance.now() : Date.now()))),
      );
      trackEvent({ event_name: "save_error", step: "basic", meta_json: JSON.stringify({ latency_ms: latencyMs }) });
    },
  });

  const autoSaveMutation = useMutation({
    retry: false,
    onMutate: () => {
      setSyncStatus("saving");
    },
    mutationFn: async () => {
      const startedAt = typeof performance !== "undefined" ? performance.now() : Date.now();
      const data = await persistProfile("resume_autosave");
      const latencyMs = Math.max(0, Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - startedAt));
      return { data, latencyMs };
    },
    onSuccess: ({ data, latencyMs }) => {
      queryClient.setQueryData(["resume", "profile"], data);
      serverUpdatedAtRef.current = Number(data.updated_at || serverUpdatedAtRef.current);
      if (syncFpRef.current === currentFingerprint) {
        setLocalDirty(false);
        localDirtyRef.current = false;
      }
      setHasConflict(false);
      conflictRef.current = false;
      setSyncStatus("synced");
      trackEvent({ event_name: "autosave_success", step: STEP_ITEMS[step]?.id || "basic", meta_json: JSON.stringify({ latency_ms: latencyMs }) });
    },
    onError: () => {
      setSyncStatus("error");
      trackEvent({ event_name: "autosave_error", step: STEP_ITEMS[step]?.id || "basic" });
    },
  });

  const sendMutation = useMutation({
    retry: false,
    onMutate: () => {
      sendStartMsRef.current = typeof performance !== "undefined" ? performance.now() : Date.now();
    },
    mutationFn: async () => {
      await persistProfile("resume_send_persist");
      const { data } = await client.post<{ ok: boolean; message: string }>("/resume/send-telegram", {
        template_id: selectedTemplate,
      });
      return data;
    },
    onSuccess: (data) => {
      setInfo(data.message || "Resume Telegramga yuborildi.");
      queryClient.invalidateQueries({ queryKey: ["resume", "profile"] });
      const latencyMs = Math.max(
        0,
        Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - (sendStartMsRef.current ?? (typeof performance !== "undefined" ? performance.now() : Date.now()))),
      );
      trackEvent({ event_name: "send_success", step: "final", meta_json: JSON.stringify({ latency_ms: latencyMs }) });
    },
    onError: () => {
      setInfo("Yuborishda xatolik bo'ldi.");
      const latencyMs = Math.max(
        0,
        Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - (sendStartMsRef.current ?? (typeof performance !== "undefined" ? performance.now() : Date.now()))),
      );
      trackEvent({ event_name: "send_error", step: "final", meta_json: JSON.stringify({ latency_ms: latencyMs }) });
    },
  });

  const isBusy = saveMutation.isPending || sendMutation.isPending;

  const resumeCorpus = useMemo(() => {
    const exp = profile.experiences.map((item) => [item.role, item.company, item.description].join(" ")).join(" ");
    const edu = profile.educations.map((item) => [item.school, item.degree, item.description].join(" ")).join(" ");
    const skills = profile.skills.join(" ");
    return [profile.full_name, profile.position, profile.summary, exp, edu, skills].join(" ").toLowerCase();
  }, [profile]);

  const topKeywords = useMemo(() => extractTopKeywords(jobDescription), [jobDescription]);
  const missingKeywords = useMemo(
    () => topKeywords.filter((keyword) => !resumeCorpus.includes(keyword)).slice(0, 8),
    [topKeywords, resumeCorpus],
  );

  const previewState = useDebouncedValue(
    {
      profile,
      selectedTemplate,
      accentColor,
    },
    280,
  );

  const isStepDone = (id: StepId): boolean => {
    if (id === "basic") return Boolean(profile.full_name.trim() && profile.position.trim());
    if (id === "experience") return profile.experiences.some((x) => x.role || x.company || x.description);
    if (id === "education") return profile.educations.some((x) => x.school || x.degree || x.description);
    if (id === "skills") return profile.skills.length >= 3;
    if (id === "summary") return profile.summary.trim().length >= 40;
    if (id === "template") return Boolean(selectedTemplate);
    return false;
  };

  const validateCurrentStep = (): boolean => {
    const current = STEP_ITEMS[step]?.id;
    const nextErrors: Record<string, string> = {};
    if (current === "basic") {
      if (!profile.full_name.trim()) nextErrors.full_name = "F.I.Sh majburiy";
      if (!profile.position.trim()) nextErrors.position = "Lavozim majburiy";
      if (!profile.email.trim() && !profile.phone.trim()) nextErrors.contact = "Kamida email yoki telefon kiriting";
    }
    if (current === "experience") {
      if (profile.experiences.length === 0) nextErrors.experience = "Kamida bitta ish tajribasi kiriting";
      if (profile.experiences.some((x) => !x.role.trim() || !x.company.trim())) {
        nextErrors.experience = "Har bir tajribada lavozim va kompaniya kiriting";
      }
    }
    if (current === "education") {
      if (profile.educations.length === 0) nextErrors.education = "Kamida bitta ta'lim yozuvi kiriting";
    }
    if (current === "skills" && profile.skills.length < 3) {
      nextErrors.skills = "Kamida 3 ta ko'nikma kiriting";
    }
    if (current === "summary" && profile.summary.trim().length < 40) {
      nextErrors.summary = "Summary kamida 40 ta belgidan iborat bo'lsin";
    }
    if (current === "template" && !selectedTemplate) {
      nextErrors.template = "Shablon tanlang";
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const goNext = () => {
    if (!validateCurrentStep()) return;
    setStep((prev) => Math.min(prev + 1, STEP_ITEMS.length - 1));
  };

  const goPrev = () => setStep((prev) => Math.max(prev - 1, 0));

  const updateExperience = (idx: number, key: keyof ResumeExperienceItem, value: string) => {
    setProfile((prev) => {
      const next = [...prev.experiences];
      next[idx] = { ...next[idx], [key]: value };
      return { ...prev, experiences: next };
    });
    markDirty();
  };

  const updateEducation = (idx: number, key: keyof ResumeEducationItem, value: string) => {
    setProfile((prev) => {
      const next = [...prev.educations];
      next[idx] = { ...next[idx], [key]: value };
      return { ...prev, educations: next };
    });
    markDirty();
  };

  const appendSuggestion = (idx: number, text: string) => {
    setProfile((prev) => {
      const next = [...prev.experiences];
      const old = next[idx]?.description?.trim() || "";
      next[idx] = {
        ...next[idx],
        description: old ? `${old}\n- ${text}` : `- ${text}`,
      };
      return { ...prev, experiences: next };
    });
    markDirty();
  };

  const syncLabel =
    syncStatus === "saving"
      ? "Auto-save: saqlanmoqda..."
      : syncStatus === "synced"
        ? "Auto-save: sinxron"
        : syncStatus === "error"
          ? "Auto-save: xatolik"
          : "Auto-save: kutish";

  if (authHintAvailable && profileQuery.isLoading && !hydratedRef.current) {
    return <div className="card p-4 text-sm text-slate-500">Yuklanmoqda...</div>;
  }

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-brand-600" />
            <h2 className="text-sm font-semibold text-slate-800">Resume Wizard</h2>
          </div>
          <span className={`text-xs ${syncStatus === "error" ? "text-red-600" : "text-slate-500"}`}>{syncLabel}</span>
        </div>
        <p className="mt-2 text-sm text-slate-600">Step-by-step to'ldiring, live previewdan darhol natijani ko'ring.</p>
        {hasConflict && (
          <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Serverda sizdan tashqari yangilanish bor. Local va server versiya to'qnashmoqda.
            <button
              className="ml-2 font-semibold text-amber-900 underline"
              onClick={() => {
                if (profileQuery.data) {
                  applyServerPayload(profileQuery.data);
                  setInfo("Server versiyasi yuklandi.");
                }
              }}
            >
              Server versiyasini yuklash
            </button>
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)_320px]">
        <aside className="card p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Qadamlar</p>
          <div className="space-y-1">
            {STEP_ITEMS.map((item, idx) => (
              <button
                key={item.id}
                onClick={() => setStep(idx)}
                className={`tap-target flex w-full items-center justify-between rounded-lg px-2 py-2 text-sm ${
                  step === idx ? "bg-brand-50 text-brand-700" : "text-slate-600"
                }`}
              >
                <span>{idx + 1}. {item.label}</span>
                {isStepDone(item.id) && <CheckCircle2 size={14} className="text-emerald-600" />}
              </button>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-slate-500">Progress: {Math.round((STEP_ITEMS.filter((x) => isStepDone(x.id)).length / STEP_ITEMS.length) * 100)}%</p>
        </aside>

        <section className="space-y-4">
          {step === 0 && (
            <section className="card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-800">Asosiy ma'lumotlar</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="F.I.Sh" value={profile.full_name} onChange={(e) => { setProfile((p) => ({ ...p, full_name: e.target.value })); markDirty(); }} />
                <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Lavozim" value={profile.position} onChange={(e) => { setProfile((p) => ({ ...p, position: e.target.value })); markDirty(); }} />
                <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Telefon" value={profile.phone} onChange={(e) => { setProfile((p) => ({ ...p, phone: e.target.value })); markDirty(); }} />
                <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Email" value={profile.email} onChange={(e) => { setProfile((p) => ({ ...p, email: e.target.value })); markDirty(); }} />
                <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Manzil" value={profile.location} onChange={(e) => { setProfile((p) => ({ ...p, location: e.target.value })); markDirty(); }} />
                <input className="tap-target rounded-xl border border-slate-300 px-3 py-2 text-sm" placeholder="Portfolio / LinkedIn" value={profile.website} onChange={(e) => { setProfile((p) => ({ ...p, website: e.target.value })); markDirty(); }} />
              </div>
              {errors.full_name && <p className="text-xs text-red-600">{errors.full_name}</p>}
              {errors.position && <p className="text-xs text-red-600">{errors.position}</p>}
              {errors.contact && <p className="text-xs text-red-600">{errors.contact}</p>}
            </section>
          )}

          {step === 1 && (
            <section className="card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-800">Ish tajribasi</h3>
                <button
                  className="tap-target rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700"
                  onClick={() => {
                    setProfile((p) => ({ ...p, experiences: [...p.experiences, { ...EMPTY_EXPERIENCE }] }));
                    markDirty();
                  }}
                >
                  + Qo'shish
                </button>
              </div>

              {profile.experiences.map((exp, idx) => (
                <div key={idx} className="rounded-xl border border-slate-200 p-3 space-y-2">
                  <div className="grid gap-2 md:grid-cols-2">
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Lavozim" value={exp.role} onChange={(e) => updateExperience(idx, "role", e.target.value)} />
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Kompaniya" value={exp.company} onChange={(e) => updateExperience(idx, "company", e.target.value)} />
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Boshlanish (MM/YYYY)" value={exp.start_date} onChange={(e) => updateExperience(idx, "start_date", e.target.value)} />
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Tugash (MM/YYYY)" value={exp.end_date} onChange={(e) => updateExperience(idx, "end_date", e.target.value)} />
                  </div>
                  <input className="tap-target w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Joylashuv" value={exp.location} onChange={(e) => updateExperience(idx, "location", e.target.value)} />
                  <textarea className="min-h-[90px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Natijalar va vazifalar" value={exp.description} onChange={(e) => updateExperience(idx, "description", e.target.value)} />
                  <div className="flex flex-wrap gap-2">
                    {getRoleBasedSuggestions(exp.role).map((suggestion) => (
                      <button
                        key={suggestion}
                        className="tap-target rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700"
                        onClick={() => appendSuggestion(idx, suggestion)}
                      >
                        + {suggestion.slice(0, 35)}...
                      </button>
                    ))}
                  </div>
                  {profile.experiences.length > 1 && (
                    <button
                      className="tap-target rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600"
                      onClick={() => {
                        setProfile((p) => ({ ...p, experiences: p.experiences.filter((_, i) => i !== idx) }));
                        markDirty();
                      }}
                    >
                      O'chirish
                    </button>
                  )}
                </div>
              ))}
              {errors.experience && <p className="text-xs text-red-600">{errors.experience}</p>}
            </section>
          )}

          {step === 2 && (
            <section className="card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-800">Ta'lim</h3>
                <button
                  className="tap-target rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700"
                  onClick={() => {
                    setProfile((p) => ({ ...p, educations: [...p.educations, { ...EMPTY_EDUCATION }] }));
                    markDirty();
                  }}
                >
                  + Qo'shish
                </button>
              </div>

              {profile.educations.map((edu, idx) => (
                <div key={idx} className="rounded-xl border border-slate-200 p-3 space-y-2">
                  <div className="grid gap-2 md:grid-cols-2">
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="O'quv yurti" value={edu.school} onChange={(e) => updateEducation(idx, "school", e.target.value)} />
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Daraja" value={edu.degree} onChange={(e) => updateEducation(idx, "degree", e.target.value)} />
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Boshlanish" value={edu.start_date} onChange={(e) => updateEducation(idx, "start_date", e.target.value)} />
                    <input className="tap-target rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Tugash" value={edu.end_date} onChange={(e) => updateEducation(idx, "end_date", e.target.value)} />
                  </div>
                  <textarea className="min-h-[84px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Qo'shimcha ma'lumot" value={edu.description} onChange={(e) => updateEducation(idx, "description", e.target.value)} />
                  {profile.educations.length > 1 && (
                    <button
                      className="tap-target rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600"
                      onClick={() => {
                        setProfile((p) => ({ ...p, educations: p.educations.filter((_, i) => i !== idx) }));
                        markDirty();
                      }}
                    >
                      O'chirish
                    </button>
                  )}
                </div>
              ))}
              {errors.education && <p className="text-xs text-red-600">{errors.education}</p>}
            </section>
          )}

          {step === 3 && (
            <section className="card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-800">Ko'nikmalar va tillar</h3>
              <input
                className="tap-target w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Ko'nikmalar (vergul bilan)"
                value={profile.skills.join(", ")}
                onChange={(e) => {
                  setProfile((p) => ({ ...p, skills: splitItems(e.target.value) }));
                  markDirty();
                }}
              />
              <input
                className="tap-target w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Tillar (vergul bilan)"
                value={profile.languages.join(", ")}
                onChange={(e) => {
                  setProfile((p) => ({ ...p, languages: splitItems(e.target.value) }));
                  markDirty();
                }}
              />
              {errors.skills && <p className="text-xs text-red-600">{errors.skills}</p>}
            </section>
          )}

          {step === 4 && (
            <section className="card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-800">Summary va JD moslash</h3>
              <textarea
                className="min-h-[120px] w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Qisqacha professional summary"
                value={profile.summary}
                onChange={(e) => {
                  setProfile((p) => ({ ...p, summary: e.target.value }));
                  markDirty();
                }}
              />
              {errors.summary && <p className="text-xs text-red-600">{errors.summary}</p>}

              <div className="rounded-xl border border-slate-200 p-3">
                <p className="text-xs font-semibold text-slate-700">Job description (AI-siz moslash)</p>
                <textarea
                  className="mt-2 min-h-[100px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Vakansiya matnini shu yerga qo'ying"
                  value={jobDescription}
                  onChange={(e) => {
                    setJobDescription(e.target.value);
                    markDirty();
                  }}
                />
                <div className="mt-2">
                  <p className="text-xs text-slate-500">Top keywordlar: {topKeywords.slice(0, 8).join(", ") || "-"}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {missingKeywords.map((kw) => (
                      <button
                        key={kw}
                        className="tap-target rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-700"
                        onClick={() => {
                          if (!profile.skills.some((s) => s.toLowerCase() === kw.toLowerCase())) {
                            setProfile((p) => ({ ...p, skills: [...p.skills, kw] }));
                            markDirty();
                          }
                        }}
                      >
                        + {kw}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </section>
          )}

          {step === 5 && (
            <section className="card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-slate-800">Shablon va rang</h3>
              <div className="grid gap-3 md:grid-cols-3">
                {templates.map((tpl) => {
                  const isSelected = tpl.id === selectedTemplate;
                  const previewColor = tpl.supports_color ? accentColor : tpl.palette[0] || "#111827";
                  return (
                    <button
                      key={tpl.id}
                      className={`tap-target rounded-xl border p-2 text-left ${isSelected ? "border-brand-500 bg-brand-50" : "border-slate-200"}`}
                      onClick={() => {
                        setSelectedTemplate(tpl.id);
                        markDirty();
                      }}
                    >
                      <TemplatePreview template={tpl} color={previewColor} />
                      <p className="mt-2 text-sm font-semibold text-slate-800">{tpl.title}</p>
                      <p className="text-xs text-slate-500">{tpl.description}</p>
                    </button>
                  );
                })}
              </div>

              <div className="flex flex-wrap gap-2">
                {(activeTemplate?.palette || []).map((color) => (
                  <button
                    key={color}
                    className={`tap-target h-8 w-8 rounded-full border-2 ${accentColor === color ? "border-slate-900" : "border-white"}`}
                    style={{ backgroundColor: color }}
                    onClick={() => {
                      setAccentColor(color);
                      markDirty();
                    }}
                  />
                ))}
              </div>
              {errors.template && <p className="text-xs text-red-600">{errors.template}</p>}
            </section>
          )}

          <section className="card p-4">
            <div className="grid gap-2 md:grid-cols-3">
              <button
                className="tap-target rounded-2xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700"
                disabled={isBusy || step === 0}
                onClick={goPrev}
              >
                Orqaga
              </button>

              <button
                className="tap-target rounded-2xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700"
                disabled={isBusy}
                onClick={() => saveMutation.mutate()}
              >
                {saveMutation.isPending ? "Saqlanmoqda..." : "Saqlash"}
              </button>

              <button
                className="tap-target rounded-2xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white"
                disabled={isBusy || step === STEP_ITEMS.length - 1}
                onClick={goNext}
              >
                Keyingi
              </button>
            </div>

            <button
              className="tap-target mt-2 flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white"
              disabled={isBusy}
              onClick={() => sendMutation.mutate()}
            >
              <Send size={15} />
              {sendMutation.isPending ? "Yuborilmoqda..." : "Telegramga yuborish"}
            </button>

            {Boolean(info) && (
              <p className={`mt-3 flex items-center gap-2 text-sm ${syncStatus === "error" ? "text-red-600" : "text-slate-700"}`}>
                {syncStatus === "error" ? <AlertCircle size={14} /> : <CheckCircle2 size={14} />}
                {info}
              </p>
            )}
          </section>
        </section>

        <div className="space-y-4 lg:sticky lg:top-3 lg:h-fit">
          <ResumePreview
            profile={previewState.profile}
            accentColor={previewState.accentColor}
            templateName={templates.find((x) => x.id === previewState.selectedTemplate)?.title || "Template"}
          />
        </div>
      </div>
    </div>
  );
}
