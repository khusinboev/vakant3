import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Briefcase,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileEdit,
  FileText,
  GraduationCap,
  Loader2,
  Palette,
  Plus,
  Send,
  Trash2,
  User,
  X,
  Zap,
} from "lucide-react";

import client from "../api/client";
import BottomNav from "../components/Layout/BottomNav";
import { setBackInterceptor, clearBackInterceptor } from "../hooks/useBackInterceptor";
import { useKeyboardOpen } from "../hooks/useKeyboardOpen";

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
  { id: "basic",      label: "Asosiy"   },
  { id: "experience", label: "Tajriba"  },
  { id: "education",  label: "Ta'lim"   },
  { id: "skills",     label: "Ko'nikma" },
  { id: "summary",    label: "Summary"  },
  { id: "template",   label: "Shablon"  },
];

const STEP_ICONS: Record<StepId, React.ElementType> = {
  basic:      User,
  experience: Briefcase,
  education:  GraduationCap,
  skills:     Zap,
  summary:    FileEdit,
  template:   Palette,
};

const STEP_HINTS: Record<StepId, string> = {
  basic:      "Ism, lavozim va kontakt ma'lumotlari",
  experience: "Ish tajriba va yutuqlaringizni kiriting",
  education:  "Ta'lim va malakangizni kiriting",
  skills:     "Ko'nikmalar va til bilimlaringizni kiriting",
  summary:    "Qisqacha professional tavsif yozing",
  template:   "Dizayn tanlang va rezyumeni tayyorlang",
};

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

const DEGREE_OPTIONS = [
  "O'rta ta'lim",
  "O'rta maxsus ta'lim (kollej / texnikum)",
  "Bakalavr",
  "Magistr (Master)",
  "Doktorantura (PhD)",
  "Sertifikat / Kurslar",
  "Boshqa",
];

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: CURRENT_YEAR - 1989 }, (_, i) => String(CURRENT_YEAR - i));

const STOP_WORDS = new Set([
  // English
  "the", "and", "for", "with", "from", "that", "this", "your",
  "you", "our", "will", "are", "or", "to", "in", "of", "on",
  "at", "by", "as", "an", "a", "be", "have", "has", "we", "is",
  "it", "its", "who", "all", "can", "not", "was", "but",
  // Uzbek
  "va", "bu", "bir", "biz", "ham", "uchun", "bilan", "yoki",
  "da", "bo'lgan", "bo'lib", "kerak", "kabi", "siz", "men",
  "ular", "u", "qilish", "mumkin", "bo'ladi", "bo'lsa", "ga",
  "ni", "dan", "ning", "dagi", "gi", "li", "chi",
  // Russian
  "и", "в", "на", "с", "по", "для", "из", "за", "от", "не",
  "что", "как", "это", "к", "а", "но", "или", "у", "о",
  "так", "то", "же", "вы", "мы", "он", "она", "они",
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

function triggerFileDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
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
  if (
    lower.includes("engineer") || lower.includes("developer") ||
    lower.includes("dasturchi") || lower.includes("ishlab")
  ) {
    return [
      "Asosiy jarayonlarni optimallashtirdim va javob vaqtini 30% ga kamaytirdim.",
      "Avtomatlashtirilgan testlar joriy etib, ishlab chiqarishdagi xatolarni 20% ga kamaytirdim.",
      "Kundalik foydalanuvchilar tomonidan ishlatiladigan asosiy funksiyani jamoalar bilan birgalikda topshirdim.",
    ];
  }
  if (
    lower.includes("sales") || lower.includes("manager") ||
    lower.includes("menejer") || lower.includes("savdo")
  ) {
    return [
      "Choraklik maqsadlarni 18% ga oshirib bajarilishiga erishdim.",
      "Mijozlar bilan munosabatlarni mustahkamlab, ushlanib qolish darajasini 15% ga oshirdim.",
      "Jamoa a'zolarini yo'naltirdim va yopish ko'rsatkichini yaxshiladim.",
    ];
  }
  if (lower.includes("dizayner") || lower.includes("designer") || lower.includes("ux")) {
    return [
      "Foydalanuvchi tajribasini tahlil qilib, konversiya darajasini 25% ga oshirdim.",
      "Mobil va web platformalar uchun responsive interfeys prototiplari ishlab chiqdim.",
      "Foydalanuvchi intervyu va testlari asosida mahsulot dizaynini yaxshiladim.",
    ];
  }
  return [
    "Jamoa ish jarayonlarini takomillashtirdim va o'lchanadigan biznes natijalarga erishdim.",
    "Manfaatdor tomonlar bilan hamkorlikda muhim loyihalarni o'z vaqtida topshirdim.",
    "KPI ko'rsatkichlarini kuzatib, ish sifatini aniq javobgarlik bilan yaxshiladim.",
  ];
}

// ─── UI primitives ────────────────────────────────────────────────────────────

/** Labeled field wrapper with optional error/hint */
function Field({
  label, required, error, hint, children,
}: {
  label: string; required?: boolean; error?: string; hint?: string; children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-baseline gap-1 text-xs font-semibold text-slate-600">
        {label}
        {required && <span className="text-red-500">*</span>}
        {hint   && <span className="ml-1 font-normal text-slate-400">{hint}</span>}
      </label>
      {children}
      {error && (
        <p className="flex items-center gap-1 text-xs text-red-600">
          <AlertCircle size={11} className="shrink-0" /> {error}
        </p>
      )}
    </div>
  );
}

const INPUT_CLS =
  "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm " +
  "placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 " +
  "focus:border-brand-400 transition-all";

const SELECT_CLS =
  "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-brand-400 transition-all";

const MONTHS = [
  "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
  "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
];

function StyledSelect({
  children, value, onChange, disabled, className,
}: {
  children: React.ReactNode;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div className="relative">
      <select
        className={`${SELECT_CLS} appearance-none pr-8 ${disabled ? "opacity-40 cursor-not-allowed bg-slate-50" : ""} ${className ?? ""}`}
        value={value}
        onChange={onChange}
        disabled={disabled}
      >
        {children}
      </select>
      <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
    </div>
  );
}

function MonthYearSelect({
  value, onChange, withCurrent = false,
}: {
  value: string; onChange: (v: string) => void; withCurrent?: boolean;
}) {
  const isCurrent = value === "Hozir";
  const parts    = isCurrent ? [] : (value || "").split("/");
  const selMonth = parts[0] ?? "";
  const selYear  = parts[1] ?? "";

  const update = (m: string, y: string) => {
    if (y === "current") { onChange("Hozir"); return; }
    if (!m && !y)        { onChange(""); return; }
    onChange(m && y ? `${m}/${y}` : y || "");
  };

  return (
    <div className="grid grid-cols-[5fr_6fr] gap-2">
      <StyledSelect
        value={isCurrent ? "" : selMonth}
        onChange={(e) => update(e.target.value, isCurrent ? "" : selYear)}
        disabled={isCurrent}
      >
        <option value="">Oy</option>
        {MONTHS.map((m, i) => (
          <option key={i} value={String(i + 1).padStart(2, "0")}>{m}</option>
        ))}
      </StyledSelect>
      <StyledSelect
        value={isCurrent ? "current" : selYear}
        onChange={(e) => update(isCurrent ? "" : selMonth, e.target.value)}
      >
        <option value="">Yil</option>
        {withCurrent && <option value="current">— Hozir —</option>}
        {YEARS.map((y) => (
          <option key={y} value={y}>{y}</option>
        ))}
      </StyledSelect>
    </div>
  );
}

/** Chip-style tag input — Enter or comma to add, Backspace to remove last */
function TagInput({
  tags, onAdd, onRemove, placeholder,
}: {
  tags: string[]; onAdd: (t: string) => void; onRemove: (i: number) => void; placeholder: string;
}) {
  const [val, setVal] = useState("");
  const ref = useRef<HTMLInputElement>(null);

  const commit = (raw: string) => {
    const v = raw.trim().replace(/,+$/, "");
    if (v && !tags.includes(v)) onAdd(v);
    setVal("");
  };

  return (
    <div
      className="min-h-[48px] rounded-xl border border-slate-300 bg-white p-2 flex flex-wrap gap-1.5
                 cursor-text focus-within:ring-2 focus-within:ring-brand-400 focus-within:border-brand-400 transition-all"
      onClick={() => ref.current?.focus()}
    >
      {tags.map((tag, idx) => (
        <span
          key={idx}
          className="inline-flex items-center gap-1 bg-brand-50 border border-brand-200
                     text-brand-700 text-xs px-2.5 py-1 rounded-full font-medium"
        >
          {tag}
          <button
            type="button"
            className="text-brand-400 hover:text-red-500 transition-colors leading-none"
            onClick={(e) => { e.stopPropagation(); onRemove(idx); }}
          >
            <X size={10} />
          </button>
        </span>
      ))}
      <input
        ref={ref}
        className="flex-1 min-w-[80px] outline-none text-sm bg-transparent py-0.5 placeholder:text-slate-400"
        placeholder={tags.length === 0 ? placeholder : "+qo'shish"}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") { e.preventDefault(); commit(val); }
          if (e.key === "Backspace" && !val && tags.length > 0) onRemove(tags.length - 1);
        }}
        onBlur={() => { if (val.trim()) commit(val); }}
      />
    </div>
  );
}

/** Horizontal step progress — dots + connectors */
function WizardProgress({
  steps, currentStep, isStepDone, onStepClick,
}: {
  steps: StepItem[];
  currentStep: number;
  isStepDone: (id: StepId) => boolean;
  onStepClick: (i: number) => void;
}) {
  return (
    <div className="flex items-center px-4 pb-2.5 overflow-x-auto [&::-webkit-scrollbar]:hidden">
      {steps.map((item, idx) => {
        const done      = isStepDone(item.id);
        const active    = currentStep === idx;
        const clickable = idx < currentStep || done;
        return (
          <Fragment key={item.id}>
            <button
              className="flex flex-col items-center min-w-[46px] shrink-0 disabled:cursor-default"
              onClick={() => clickable && onStepClick(idx)}
              disabled={!clickable}
            >
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-200 ${
                  active
                    ? "bg-brand-600 text-white shadow-md shadow-brand-200"
                    : done
                      ? "bg-emerald-500 text-white"
                      : idx < currentStep
                        ? "bg-slate-300 text-slate-600"
                        : "bg-slate-100 text-slate-300 border border-slate-200"
                }`}
              >
                {done && !active ? <Check size={12} /> : idx + 1}
              </div>
              <span
                className={`mt-0.5 text-[9px] font-medium whitespace-nowrap transition-colors ${
                  active ? "text-brand-600" : done ? "text-emerald-600" : "text-slate-400"
                }`}
              >
                {item.label}
              </span>
            </button>
            {idx < steps.length - 1 && (
              <div
                className={`h-0.5 flex-1 min-w-[6px] mx-0.5 rounded-full transition-all duration-500 ${
                  done ? "bg-emerald-400" : "bg-slate-200"
                }`}
              />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}

function TemplatePreview({ template, color }: { template: ResumeTemplateItem; color: string }) {
  if (template.preview_variant === "split") {
    return (
      <div className="h-16 w-full overflow-hidden rounded-lg border border-slate-200 bg-white flex">
        <div className="w-1/3" style={{ backgroundColor: color }} />
        <div className="flex-1 p-1.5">
          <div className="h-1.5 w-3/4 rounded bg-slate-300" />
          <div className="mt-1.5 h-1 w-full rounded bg-slate-200" />
          <div className="mt-1 h-1 w-4/5 rounded bg-slate-200" />
          <div className="mt-1 h-1 w-2/3 rounded bg-slate-200" />
        </div>
      </div>
    );
  }
  if (template.preview_variant === "mono") {
    return (
      <div className="h-16 w-full overflow-hidden rounded-lg border border-slate-200 bg-white p-2">
        <div className="h-1.5 w-2/3 rounded bg-slate-800" />
        <div className="mt-1.5 h-1 w-full rounded bg-slate-300" />
        <div className="mt-1 h-1 w-4/5 rounded bg-slate-300" />
        <div className="mt-1 h-1 w-3/5 rounded bg-slate-200" />
      </div>
    );
  }
  return (
    <div className="h-16 w-full overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="h-4" style={{ backgroundColor: color }} />
      <div className="p-1.5">
        <div className="h-1.5 w-1/2 rounded bg-slate-300" />
        <div className="mt-1.5 h-1 w-full rounded bg-slate-200" />
        <div className="mt-1 h-1 w-5/6 rounded bg-slate-200" />
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
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
      <div className="px-4 py-3 text-white" style={{ backgroundColor: accentColor }}>
        <p className="text-sm font-bold">{profile.full_name || "Nomsiz nomzod"}</p>
        <p className="text-xs opacity-90 mt-0.5">{profile.position || "Lavozim ko'rsatilmagan"}</p>
        <p className="text-[10px] opacity-75 mt-0.5">
          {[profile.phone, profile.email, profile.location].filter(Boolean).join(" · ") || "Kontakt kiritilmagan"}
        </p>
      </div>
      <div className="p-3 space-y-2.5 text-xs">
        {profile.summary && (
          <div>
            <p className="font-semibold text-slate-600 uppercase tracking-wide text-[9px] mb-1">Summary</p>
            <p className="text-slate-700 line-clamp-3 leading-relaxed">{profile.summary}</p>
          </div>
        )}
        {profile.experiences.length > 0 && (
          <div>
            <p className="font-semibold text-slate-600 uppercase tracking-wide text-[9px] mb-1">Tajriba</p>
            {profile.experiences.slice(0, 2).map((x, i) => (
              <p key={i} className="text-slate-700">
                {[x.role, x.company].filter(Boolean).join(" @ ") || "Tajriba"}
                {x.start_date && <span className="text-slate-400 ml-1">· {x.start_date}</span>}
              </p>
            ))}
          </div>
        )}
        {profile.skills.length > 0 && (
          <div>
            <p className="font-semibold text-slate-600 uppercase tracking-wide text-[9px] mb-1">Ko'nikmalar</p>
            <p className="text-slate-700 line-clamp-2">{profile.skills.slice(0, 8).join(", ")}</p>
          </div>
        )}
        <p className="text-[9px] text-slate-400 text-right">{templateName}</p>
      </div>
    </div>
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
  const exportStartMsRef = useRef<number | null>(null);
  const syncFpRef = useRef<string>("");
  const serverUpdatedAtRef = useRef<number>(0);
  const localDirtyRef = useRef(false);
  const conflictRef = useRef(false);
  // Refs to track mutation pending state without stale closures in setInterval
  const savePendingRef = useRef(false);
  const sendPendingRef = useRef(false);
  const autoSavePendingRef = useRef(false);

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
  const [showPreview, setShowPreview] = useState(false);
  // Stable keys for experience/education list items (avoids React key flicker on delete)
  const [expKeys, setExpKeys] = useState<string[]>([]);
  const [eduKeys, setEduKeys] = useState<string[]>([]);

  const genKey = () => `k_${Date.now()}_${Math.random().toString(36).slice(2)}`;

  // Auto-dismiss info messages after 4 s
  useEffect(() => {
    if (!info) return;
    const t = setTimeout(() => setInfo(""), 4000);
    return () => clearTimeout(t);
  }, [info]);

  const trackEvent = (payload: ResumeEventPayload) => {
    void client.post("/resume/events", payload).catch(() => undefined);
  };

  const makeIdempotencyKey = (action: string): string => {
    const rand = Math.random().toString(36).slice(2, 10);
    return `${action}:${Date.now()}:${rand}`;
  };

  // Evaluated once on mount — avoids reading localStorage on every render
  const authHintAvailable = useMemo(
    () => Boolean(
      localStorage.getItem("session_token") ||
      window.Telegram?.WebApp?.initData ||
      window.Telegram?.WebApp?.initDataUnsafe?.user?.id,
    ),
    [],
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
    setExpKeys(normalized.experiences.map(() => genKey()));
    setEduKeys(normalized.educations.map(() => genKey()));
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
    const normalized = normalizeProfile(localDraft.profile);
    setProfile(normalized);
    setExpKeys(normalized.experiences.map(() => genKey()));
    setEduKeys(normalized.educations.map(() => genKey()));
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
        const normalized = normalizeProfile(localDraft.profile);
        setProfile(normalized);
        setExpKeys(normalized.experiences.map(() => genKey()));
        setEduKeys(normalized.educations.map(() => genKey()));
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
      if (
        localDirtyRef.current &&
        !savePendingRef.current &&
        !sendPendingRef.current &&
        !autoSavePendingRef.current
      ) {
        autoSaveMutation.mutate();
      }
    }, 15000);
    return () => clearInterval(interval);
  }, [authHintAvailable]);

  const saveMutation = useMutation({
    retry: false,
    onMutate: () => {
      savePendingRef.current = true;
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
    onSettled: () => { savePendingRef.current = false; },
  });

  const autoSaveMutation = useMutation({
    retry: false,
    onMutate: () => {
      autoSavePendingRef.current = true;
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
    onSettled: () => { autoSavePendingRef.current = false; },
  });

  const sendMutation = useMutation({
    retry: false,
    onMutate: () => {
      sendPendingRef.current = true;
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
    onSettled: () => { sendPendingRef.current = false; },
  });

  const exportMutation = useMutation({
    retry: false,
    onMutate: () => {
      exportStartMsRef.current = typeof performance !== "undefined" ? performance.now() : Date.now();
    },
    mutationFn: async (format: "pdf" | "docx") => {
      await persistProfile(`resume_export_${format}_persist`);
      const response = await client.post<Blob>(
        "/resume/export",
        {
          format,
          template_id: selectedTemplate,
        },
        { responseType: "blob" },
      );
      const header = String(response.headers["content-disposition"] || "");
      const matched = /filename="?([^";]+)"?/i.exec(header);
      const filename = matched?.[1] || `resume.${format}`;
      triggerFileDownload(response.data, filename);
      return format;
    },
    onSuccess: (format) => {
      const latencyMs = Math.max(
        0,
        Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - (exportStartMsRef.current ?? (typeof performance !== "undefined" ? performance.now() : Date.now()))),
      );
      setInfo(`${format.toUpperCase()} yuklab olindi.`);
      trackEvent({ event_name: "export_success", step: "final", meta_json: JSON.stringify({ format, latency_ms: latencyMs }) });
    },
    onError: (_error, format) => {
      const latencyMs = Math.max(
        0,
        Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - (exportStartMsRef.current ?? (typeof performance !== "undefined" ? performance.now() : Date.now()))),
      );
      setInfo("Exportda xatolik bo'ldi.");
      trackEvent({ event_name: "export_error", step: "final", meta_json: JSON.stringify({ format, latency_ms: latencyMs }) });
    },
  });

  const isBusy = saveMutation.isPending || sendMutation.isPending || exportMutation.isPending;

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

  // Register back-interceptor: step > 0 → go to previous step instead of leaving page
  useEffect(() => {
    if (step > 0) {
      setBackInterceptor(() => {
        // First close keyboard if open
        const active = document.activeElement as HTMLElement | null;
        if (
          active &&
          (active.tagName === "INPUT" ||
            active.tagName === "TEXTAREA" ||
            active.tagName === "SELECT")
        ) {
          active.blur();
          return true;
        }
        setStep((prev) => Math.max(prev - 1, 0));
        return true;
      });
    } else {
      clearBackInterceptor();
    }
    return () => clearBackInterceptor();
  }, [step]);

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

  if (authHintAvailable && profileQuery.isLoading && !hydratedRef.current) {
    return (
      <div className="flex items-center justify-center gap-3 py-20 text-slate-500">
        <Loader2 size={20} className="animate-spin" />
        <span className="text-sm">Yuklanmoqda...</span>
      </div>
    );
  }

  const currentStepItem = STEP_ITEMS[step];
  const StepIcon        = STEP_ICONS[currentStepItem?.id ?? "basic"];
  const isLastStep      = step === STEP_ITEMS.length - 1;
  const progressPct     = Math.round(
    (STEP_ITEMS.filter((x) => isStepDone(x.id)).length / STEP_ITEMS.length) * 100,
  );
  const syncLabel =
    syncStatus === "saving" ? "Saqlanmoqda..." :
    syncStatus === "synced" ? "Saqlandi"       :
    syncStatus === "error"  ? "Xatolik"        : "Kutish";

  const keyboardOpen = useKeyboardOpen();
  // When keyboard is closed, reserve space at the bottom so the fixed BottomNav
  // doesn't overlap the action bar.  When keyboard is open BottomNav auto-hides
  // so no reservation is needed.
  const bottomClearance = keyboardOpen
    ? "0px"
    : "calc(3.5rem + var(--bottom-safe, 0px))";

  return (
    <div
      className="flex flex-col bg-slate-50 overflow-x-hidden"
      style={{
        height: "var(--tg-viewport-height, var(--app-viewport-height, 100dvh))",
        paddingBottom: bottomClearance,
      }}
    >

      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 shrink-0 bg-white border-b border-slate-200 shadow-sm">

        {/* Bandlik.uz brand bar */}
        <div className="flex items-center justify-center border-b border-slate-100"
          style={{ paddingTop: "calc(0.75rem + var(--tg-content-safe-area-top, 0px))", paddingBottom: "0.625rem" }}>
          <Link to="/app" className="font-display text-xl font-extrabold text-brand-700">Bandlik.uz</Link>
        </div>

        {/* Title row */}
        <div className="flex items-center justify-between px-4 pt-2 pb-1.5">
          <div className="flex items-center gap-2">
            <FileText size={15} className="text-brand-600 shrink-0" />
            <span className="text-sm font-bold text-slate-800">Resume Wizard</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-brand-600 transition-colors"
              onClick={() => setShowPreview((p) => !p)}
            >
              <Eye size={13} />
              <span>Preview</span>
            </button>
            <span
              className={`flex items-center gap-1 text-[10px] font-semibold ${
                syncStatus === "saving" ? "text-amber-500" :
                syncStatus === "synced" ? "text-emerald-600" :
                syncStatus === "error"  ? "text-red-500"    : "text-slate-300"
              }`}
            >
              {syncStatus === "saving" ? <Loader2 size={10} className="animate-spin" /> :
               syncStatus === "synced" ? <Check size={10} /> :
               syncStatus === "error"  ? <AlertCircle size={10} /> : null}
              {syncLabel}
            </span>
          </div>
        </div>

        {/* Step dots */}
        <WizardProgress
          steps={STEP_ITEMS}
          currentStep={step}
          isStepDone={isStepDone}
          onStepClick={setStep}
        />

        {/* Linear progress bar */}
        <div className="h-[3px] bg-slate-100">
          <div
            className="h-full bg-emerald-500 transition-all duration-700 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* ── CONFLICT BANNER ───────────────────────────────────────────────── */}
      {hasConflict && (
        <div className="flex items-start gap-2 bg-amber-50 border-b border-amber-200 px-4 py-2.5">
          <AlertCircle size={14} className="text-amber-600 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-800 flex-1">
            Server va lokal ma'lumotlar to'qnashmoqda.{" "}
            <button
              className="underline font-semibold"
              onClick={() => { if (profileQuery.data) { applyServerPayload(profileQuery.data); setInfo("Server versiyasi yuklandi."); } }}
            >
              Server versiyasini yuklash
            </button>
          </p>
        </div>
      )}

      {/* ── CONTENT ──────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0 pb-2">

        {/* Step header */}
        <div className="flex items-center gap-3 px-4 pt-4 pb-3">
          <div className="p-2.5 rounded-2xl bg-brand-50 border border-brand-100 shrink-0">
            <StepIcon size={20} className="text-brand-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold text-slate-800">{currentStepItem?.label}</h2>
            <p className="text-xs text-slate-500 mt-0.5 truncate">{STEP_HINTS[currentStepItem?.id]}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[11px] font-semibold text-slate-400">{step + 1}/{STEP_ITEMS.length}</p>
            <p className="text-[11px] font-bold text-emerald-600">{progressPct}%</p>
          </div>
        </div>

        {/* Step content — key triggers re-mount animation on step change */}
        <div key={`step-${step}`} className="px-4 space-y-4 step-enter">

          {/* ═══ STEP 0: Basic ══════════════════════════════════════════ */}
          {step === 0 && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="F.I.Sh" required error={errors.full_name}>
                  <input className={INPUT_CLS} placeholder="Abdullayev Ali" value={profile.full_name}
                    onChange={(e) => { setProfile((p) => ({ ...p, full_name: e.target.value })); markDirty(); }} />
                </Field>
                <Field label="Lavozim" required error={errors.position}>
                  <input className={INPUT_CLS} placeholder="Frontend Dev" value={profile.position}
                    onChange={(e) => { setProfile((p) => ({ ...p, position: e.target.value })); markDirty(); }} />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Telefon" error={errors.contact}>
                  <input className={INPUT_CLS} placeholder="+998 90 123 45 67" value={profile.phone}
                    onChange={(e) => { setProfile((p) => ({ ...p, phone: e.target.value })); markDirty(); }} />
                </Field>
                <Field label="Email">
                  <input className={INPUT_CLS} placeholder="ali@email.com" type="email" value={profile.email}
                    onChange={(e) => { setProfile((p) => ({ ...p, email: e.target.value })); markDirty(); }} />
                </Field>
              </div>
              <Field label="Manzil">
                <input className={INPUT_CLS} placeholder="Toshkent, O'zbekiston" value={profile.location}
                  onChange={(e) => { setProfile((p) => ({ ...p, location: e.target.value })); markDirty(); }} />
              </Field>
              <Field label="Portfolio / LinkedIn" hint="(ixtiyoriy)">
                <input className={INPUT_CLS} placeholder="linkedin.com/in/username" value={profile.website}
                  onChange={(e) => { setProfile((p) => ({ ...p, website: e.target.value })); markDirty(); }} />
              </Field>
            </div>
          )}

          {/* ═══ STEP 1: Experience ══════════════════════════════════════ */}
          {step === 1 && (
            <div className="space-y-3">
              {profile.experiences.length === 0 && (
                <div className="rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center bg-white">
                  <Briefcase size={36} className="mx-auto text-slate-300 mb-3" />
                  <p className="text-sm font-semibold text-slate-500">Ish tajribasi qo'shilmagan</p>
                  <p className="text-xs text-slate-400 mt-1">Quyidagi tugmani bosib qo'shing</p>
                </div>
              )}
              {profile.experiences.map((exp, idx) => (
                <div key={expKeys[idx] ?? String(idx)} className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
                  <div className="flex items-center gap-3 px-4 py-3 bg-slate-50 border-b border-slate-200">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-slate-800 truncate">
                        {exp.role || exp.company ? `${exp.role || "Lavozim"} @ ${exp.company || "Kompaniya"}` : `Tajriba ${idx + 1}`}
                      </p>
                      {(exp.start_date || exp.end_date) && (
                        <p className="text-xs text-slate-400 mt-0.5">{[exp.start_date, exp.end_date].filter(Boolean).join(" – ")}</p>
                      )}
                    </div>
                    <button
                      className="p-2 rounded-xl border border-red-200 text-red-400 hover:bg-red-50 shrink-0 transition-colors"
                      onClick={() => {
                        setProfile((p) => ({ ...p, experiences: p.experiences.filter((_, i) => i !== idx) }));
                        setExpKeys((k) => k.filter((_, i) => i !== idx));
                        markDirty();
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="p-4 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Lavozim">
                        <input className={INPUT_CLS} placeholder="Senior Engineer" value={exp.role}
                          onChange={(e) => updateExperience(idx, "role", e.target.value)} />
                      </Field>
                      <Field label="Kompaniya">
                        <input className={INPUT_CLS} placeholder="Google Inc." value={exp.company}
                          onChange={(e) => updateExperience(idx, "company", e.target.value)} />
                      </Field>
                      <Field label="Boshlanish">
                        <MonthYearSelect
                          value={exp.start_date}
                          onChange={(v) => updateExperience(idx, "start_date", v)}
                        />
                      </Field>
                      <Field label="Tugash">
                        <MonthYearSelect
                          value={exp.end_date}
                          onChange={(v) => updateExperience(idx, "end_date", v)}
                          withCurrent
                        />
                      </Field>
                    </div>
                    <Field label="Joylashuv" hint="(ixtiyoriy)">
                      <input className={INPUT_CLS} placeholder="Toshkent" value={exp.location}
                        onChange={(e) => updateExperience(idx, "location", e.target.value)} />
                    </Field>
                    <Field label="Natijalar va vazifalar">
                      <textarea
                        className={`${INPUT_CLS} min-h-[96px] resize-none`}
                        placeholder="- Asosiy yutuqlar va vazifalar..."
                        value={exp.description}
                        onChange={(e) => updateExperience(idx, "description", e.target.value)}
                      />
                    </Field>
                    <div className="flex flex-wrap gap-1.5">
                      {getRoleBasedSuggestions(exp.role).slice(0, 2).map((sug) => (
                        <button
                          key={sug}
                          className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700 text-left"
                          onClick={() => appendSuggestion(idx, sug)}
                        >
                          + {sug.slice(0, 38)}…
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
              {errors.experience && (
                <p className="flex items-center gap-1.5 text-xs text-red-600 px-1">
                  <AlertCircle size={12} className="shrink-0" /> {errors.experience}
                </p>
              )}
              <button
                className="tap-target w-full flex items-center justify-center gap-2 rounded-2xl
                           border-2 border-dashed border-brand-300 bg-brand-50 py-3.5
                           text-sm font-semibold text-brand-600 hover:bg-brand-100 transition-colors"
                onClick={() => { setProfile((p) => ({ ...p, experiences: [...p.experiences, { ...EMPTY_EXPERIENCE }] })); setExpKeys((k) => [...k, genKey()]); markDirty(); }}
              >
                <Plus size={16} /> Tajriba qo'shish
              </button>
            </div>
          )}

          {/* ═══ STEP 2: Education ════════════════════════════════════════ */}
          {step === 2 && (
            <div className="space-y-3">
              {profile.educations.length === 0 && (
                <div className="rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center bg-white">
                  <GraduationCap size={36} className="mx-auto text-slate-300 mb-3" />
                  <p className="text-sm font-semibold text-slate-500">Ta'lim ma'lumoti qo'shilmagan</p>
                </div>
              )}
              {profile.educations.map((edu, idx) => (
                <div key={eduKeys[idx] ?? String(idx)} className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
                  <div className="flex items-center gap-3 px-4 py-3 bg-slate-50 border-b border-slate-200">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-slate-800 truncate">
                        {edu.school || edu.degree ? `${edu.school || "O'quv yurti"} — ${edu.degree || "Daraja"}` : `Ta'lim ${idx + 1}`}
                      </p>
                      {(edu.start_date || edu.end_date) && (
                        <p className="text-xs text-slate-400 mt-0.5">{[edu.start_date, edu.end_date].filter(Boolean).join(" – ")}</p>
                      )}
                    </div>
                    <button
                      className="p-2 rounded-xl border border-red-200 text-red-400 hover:bg-red-50 shrink-0 transition-colors"
                      onClick={() => {
                        setProfile((p) => ({ ...p, educations: p.educations.filter((_, i) => i !== idx) }));
                        setEduKeys((k) => k.filter((_, i) => i !== idx));
                        markDirty();
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="p-4 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="O'quv yurti">
                        <input className={INPUT_CLS} placeholder="Toshkent DTU" value={edu.school}
                          onChange={(e) => updateEducation(idx, "school", e.target.value)} />
                      </Field>
                      <Field label="Daraja">
                        <StyledSelect
                          value={edu.degree}
                          onChange={(e) => updateEducation(idx, "degree", e.target.value)}
                        >
                          <option value="">Daraja tanlang</option>
                          {DEGREE_OPTIONS.map((d) => (
                            <option key={d} value={d}>{d}</option>
                          ))}
                        </StyledSelect>
                      </Field>
                      <Field label="Boshlanish">
                        <MonthYearSelect
                          value={edu.start_date}
                          onChange={(v) => updateEducation(idx, "start_date", v)}
                        />
                      </Field>
                      <Field label="Tugash">
                        <MonthYearSelect
                          value={edu.end_date}
                          onChange={(v) => updateEducation(idx, "end_date", v)}
                          withCurrent
                        />
                      </Field>
                    </div>
                    <Field label="Qo'shimcha ma'lumot" hint="(ixtiyoriy)">
                      <textarea
                        className={`${INPUT_CLS} min-h-[72px] resize-none`}
                        placeholder="Diplom, mukofotlar, loyihalar..."
                        value={edu.description}
                        onChange={(e) => updateEducation(idx, "description", e.target.value)}
                      />
                    </Field>
                  </div>
                </div>
              ))}
              {errors.education && (
                <p className="flex items-center gap-1.5 text-xs text-red-600 px-1">
                  <AlertCircle size={12} className="shrink-0" /> {errors.education}
                </p>
              )}
              <button
                className="tap-target w-full flex items-center justify-center gap-2 rounded-2xl
                           border-2 border-dashed border-brand-300 bg-brand-50 py-3.5
                           text-sm font-semibold text-brand-600 hover:bg-brand-100 transition-colors"
                onClick={() => { setProfile((p) => ({ ...p, educations: [...p.educations, { ...EMPTY_EDUCATION }] })); setEduKeys((k) => [...k, genKey()]); markDirty(); }}
              >
                <Plus size={16} /> Ta'lim qo'shish
              </button>
            </div>
          )}

          {/* ═══ STEP 3: Skills ═══════════════════════════════════════════ */}
          {step === 3 && (
            <div className="space-y-4">
              <Field label="Ko'nikmalar" hint="— Enter yoki vergul bilan ajrating" error={errors.skills}>
                <TagInput
                  tags={profile.skills}
                  onAdd={(t) => { setProfile((p) => ({ ...p, skills: [...p.skills, t] })); markDirty(); }}
                  onRemove={(i) => { setProfile((p) => ({ ...p, skills: p.skills.filter((_, j) => j !== i) })); markDirty(); }}
                  placeholder="JavaScript, React, Python..."
                />
                <p className="text-xs text-slate-400">
                  {profile.skills.length} ta ko'nikma
                  {profile.skills.length < 3 && <span className="text-amber-500 ml-1">(kamida 3 ta)</span>}
                </p>
              </Field>

              <Field label="Tillar" hint="— Enter yoki vergul bilan ajrating">
                <TagInput
                  tags={profile.languages}
                  onAdd={(t) => { setProfile((p) => ({ ...p, languages: [...p.languages, t] })); markDirty(); }}
                  onRemove={(i) => { setProfile((p) => ({ ...p, languages: p.languages.filter((_, j) => j !== i) })); markDirty(); }}
                  placeholder="O'zbek, Ingliz, Rus..."
                />
              </Field>

              {profile.position && (
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-semibold text-slate-600 mb-2.5">«{profile.position}» uchun tavsiyalar</p>
                  <div className="flex flex-wrap gap-1.5">
                    {["JavaScript","TypeScript","React","Node.js","Python","SQL","Git","Docker","REST API","Agile"]
                      .filter((s) => !profile.skills.some((x) => x.toLowerCase() === s.toLowerCase()))
                      .slice(0, 8)
                      .map((kw) => (
                        <button
                          key={kw}
                          className="rounded-full border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs text-brand-600 font-medium"
                          onClick={() => { setProfile((p) => ({ ...p, skills: [...p.skills, kw] })); markDirty(); }}
                        >
                          + {kw}
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ═══ STEP 4: Summary ══════════════════════════════════════════ */}
          {step === 4 && (
            <div className="space-y-4">
              <Field label="Professional summary" error={errors.summary}>
                <textarea
                  className={`${INPUT_CLS} min-h-[130px] resize-none`}
                  placeholder="5+ yillik tajribaga ega dasturchi sifatida..."
                  value={profile.summary}
                  onChange={(e) => { setProfile((p) => ({ ...p, summary: e.target.value })); markDirty(); }}
                />
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Kamida 40 ta belgi</span>
                  <span className={`text-xs font-semibold ${profile.summary.length >= 40 ? "text-emerald-600" : "text-slate-400"}`}>
                    {profile.summary.length} belgi
                  </span>
                </div>
              </Field>

              <div className="rounded-2xl border border-amber-200 bg-amber-50 overflow-hidden">
                <div className="px-4 py-3 border-b border-amber-200">
                  <p className="text-xs font-bold text-amber-800">Vakansiya bo'yicha moslash</p>
                  <p className="text-[11px] text-amber-600 mt-0.5">Vakansiya matnini kiriting — kalit so'zlarni tavsiya qilamiz</p>
                </div>
                <div className="p-4 space-y-3">
                  <textarea
                    className={`${INPUT_CLS} min-h-[90px] resize-none border-amber-300 focus:ring-amber-400 focus:border-amber-400`}
                    placeholder="Ish e'loni matnini shu yerga nusxalang..."
                    value={jobDescription}
                    onChange={(e) => { setJobDescription(e.target.value); markDirty(); }}
                  />
                  {topKeywords.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-500">
                        Top kalit so'zlar: <span className="font-medium">{topKeywords.slice(0, 6).join(", ")}</span>
                      </p>
                      {missingKeywords.length > 0 ? (
                        <div>
                          <p className="text-xs font-semibold text-amber-700 mb-1.5">Rezyumeda yo'q kalit so'zlar:</p>
                          <div className="flex flex-wrap gap-1.5">
                            {missingKeywords.map((kw) => (
                              <button
                                key={kw}
                                className="rounded-full border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-medium text-amber-700"
                                onClick={() => { setProfile((p) => ({ ...p, skills: [...p.skills, kw] })); markDirty(); }}
                              >
                                + {kw}
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p className="flex items-center gap-1 text-xs text-emerald-700 font-semibold">
                          <Check size={12} /> Barcha kalit so'zlar rezyumeda mavjud!
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ═══ STEP 5: Template ═════════════════════════════════════════ */}
          {step === 5 && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-2.5">
                {templates.map((tpl) => {
                  const sel = tpl.id === selectedTemplate;
                  const col = tpl.supports_color ? accentColor : tpl.palette[0] || "#111827";
                  return (
                    <button
                      key={tpl.id}
                      className={`tap-target rounded-2xl border-2 p-2 text-left transition-all ${
                        sel ? "border-brand-500 bg-brand-50 shadow-md shadow-brand-100" : "border-slate-200 bg-white"
                      }`}
                      onClick={() => { setSelectedTemplate(tpl.id); markDirty(); }}
                    >
                      <TemplatePreview template={tpl} color={col} />
                      <div className="mt-2 flex items-center justify-between gap-1">
                        <p className="text-xs font-bold text-slate-800 leading-tight truncate">{tpl.title}</p>
                        {sel && <Check size={12} className="text-brand-600 shrink-0" />}
                      </div>
                    </button>
                  );
                })}
              </div>

              {activeTemplate?.supports_color && (
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-semibold text-slate-600 mb-3">Rang tanlash</p>
                  <div className="flex gap-3 flex-wrap">
                    {(activeTemplate.palette || []).map((color) => (
                      <button
                        key={color}
                        className={`w-9 h-9 rounded-full border-[3px] transition-all ${
                          accentColor === color ? "border-slate-800 scale-110 shadow-md" : "border-white shadow"
                        }`}
                        style={{ backgroundColor: color }}
                        onClick={() => { setAccentColor(color); markDirty(); }}
                      />
                    ))}
                  </div>
                </div>
              )}

              {errors.template && (
                <p className="flex items-center gap-1 text-xs text-red-600">
                  <AlertCircle size={11} /> {errors.template}
                </p>
              )}

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Live Preview</p>
                <ResumePreview
                  profile={previewState.profile}
                  accentColor={previewState.accentColor}
                  templateName={templates.find((x) => x.id === previewState.selectedTemplate)?.title || "Template"}
                />
              </div>

              <div className="space-y-2.5 pt-1">
                <p className="text-xs font-semibold text-slate-600">Yuborish va yuklab olish</p>
                <button
                  className="tap-target w-full flex items-center justify-center gap-2 rounded-2xl
                             bg-emerald-600 py-4 text-sm font-bold text-white
                             shadow-lg shadow-emerald-200 disabled:opacity-60"
                  disabled={isBusy}
                  onClick={() => sendMutation.mutate()}
                >
                  {sendMutation.isPending
                    ? <><Loader2 size={16} className="animate-spin" /> Yuborilmoqda...</>
                    : <><Send size={16} /> Telegramga yuborish</>}
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    className="tap-target flex items-center justify-center gap-1.5 rounded-2xl
                               border border-slate-300 bg-white py-3 text-sm font-semibold
                               text-slate-700 disabled:opacity-60"
                    disabled={isBusy}
                    onClick={() => exportMutation.mutate("pdf")}
                  >
                    {exportMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                    PDF
                  </button>
                  <button
                    className="tap-target flex items-center justify-center gap-1.5 rounded-2xl
                               border border-slate-300 bg-white py-3 text-sm font-semibold
                               text-slate-700 disabled:opacity-60"
                    disabled={isBusy}
                    onClick={() => exportMutation.mutate("docx")}
                  >
                    {exportMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                    DOCX
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Preview toggle — steps 0–4 */}
          {showPreview && step < STEP_ITEMS.length - 1 && (
            <div className="pt-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Live Preview</p>
              <ResumePreview
                profile={previewState.profile}
                accentColor={previewState.accentColor}
                templateName={templates.find((x) => x.id === previewState.selectedTemplate)?.title || "Template"}
              />
            </div>
          )}

          {/* Info message */}
          {Boolean(info) && (
            <div
              className={`flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium ${
                syncStatus === "error"
                  ? "bg-red-50 text-red-700 border border-red-200"
                  : "bg-emerald-50 text-emerald-700 border border-emerald-200"
              }`}
            >
              {syncStatus === "error" ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
              {info}
            </div>
          )}
        </div>
      </div>

      {/* ── STEP ACTION BAR ──────────────────────────────────────────────── */}
      <div className="shrink-0 bg-white border-t border-slate-100 px-3 py-2">
        <div className="flex items-center gap-2">

          {/* Back */}
          <button
            className={`flex items-center justify-center w-10 h-10 rounded-xl border transition-colors shrink-0 ${
              step === 0
                ? "border-slate-100 text-slate-300 cursor-default"
                : "border-slate-200 text-slate-600 active:bg-slate-100"
            }`}
            onClick={goPrev}
            disabled={step === 0 || isBusy}
          >
            <ChevronLeft size={18} />
          </button>

          {/* Save status pill */}
          <button
            className={`flex flex-1 items-center justify-center gap-1.5 h-10 rounded-xl border text-xs font-semibold transition-all ${
              saveMutation.isPending
                ? "border-amber-200 bg-amber-50 text-amber-600"
                : localDirty
                  ? "border-brand-200 bg-brand-50 text-brand-700"
                  : "border-slate-100 bg-slate-50 text-slate-400"
            }`}
            onClick={() => saveMutation.mutate()}
            disabled={isBusy}
          >
            {saveMutation.isPending ? (
              <><Loader2 size={12} className="animate-spin" /> Saqlanmoqda</>
            ) : localDirty ? (
              "Saqlash"
            ) : (
              <><Check size={12} /> Saqlandi</>
            )}
          </button>

          {/* Next / Finish */}
          {!isLastStep ? (
            <button
              className="flex items-center gap-1.5 h-10 px-4 rounded-xl bg-brand-600 text-white
                         text-sm font-bold shadow shadow-brand-200 disabled:opacity-50 shrink-0"
              onClick={goNext}
              disabled={isBusy}
            >
              Keyingi <ChevronRight size={16} />
            </button>
          ) : (
            <button
              className="flex items-center gap-1.5 h-10 px-4 rounded-xl bg-emerald-600 text-white
                         text-sm font-bold shadow shadow-emerald-200 disabled:opacity-50 shrink-0"
              onClick={() => sendMutation.mutate()}
              disabled={isBusy}
            >
              <Send size={14} /> Yuborish
            </button>
          )}
        </div>
      </div>

      {/* ── BOTTOM NAV (fixed – auto-hides on keyboard open) ─────────────── */}
      <BottomNav fixed={true} />
    </div>
  );
}

