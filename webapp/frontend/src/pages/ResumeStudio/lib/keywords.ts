import type { TranslationKey } from "../../../i18n";

/** Words that carry no signal when mining a job ad for keywords. */
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

/** The 20 most frequent meaningful words of a pasted job ad. */
export function extractTopKeywords(jobDescription: string): string[] {
  const words = (jobDescription.toLowerCase().match(/[a-zA-Z][a-zA-Z0-9+.#-]{2,}/g) || []).filter(
    (word) => !STOP_WORDS.has(word),
  );
  const freq = new Map<string, number>();
  for (const word of words) freq.set(word, (freq.get(word) || 0) + 1);
  return [...freq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([word]) => word);
}

const SUGGESTION_GROUPS: Array<{ match: string[]; keys: TranslationKey[] }> = [
  {
    match: ["engineer", "developer", "dasturchi", "ishlab", "разработ", "программ"],
    keys: ["resume.suggest.dev1", "resume.suggest.dev2", "resume.suggest.dev3"],
  },
  {
    match: ["sales", "manager", "menejer", "savdo", "продаж", "менеджер"],
    keys: ["resume.suggest.sales1", "resume.suggest.sales2", "resume.suggest.sales3"],
  },
  {
    match: ["dizayner", "designer", "ux", "дизайн"],
    keys: ["resume.suggest.design1", "resume.suggest.design2", "resume.suggest.design3"],
  },
];

const GENERIC_KEYS: TranslationKey[] = [
  "resume.suggest.generic1",
  "resume.suggest.generic2",
  "resume.suggest.generic3",
];

/** Translation keys of the bullet suggestions offered for a job title. */
export function roleSuggestionKeys(role: string): TranslationKey[] {
  const lower = (role || "").toLowerCase();
  const group = SUGGESTION_GROUPS.find((item) => item.match.some((needle) => lower.includes(needle)));
  return group ? group.keys : GENERIC_KEYS;
}

/** Generic skill chips offered on the skills step. */
export const SKILL_SUGGESTIONS = [
  "JavaScript",
  "TypeScript",
  "React",
  "Node.js",
  "Python",
  "SQL",
  "Git",
  "Docker",
  "REST API",
  "Agile",
];
