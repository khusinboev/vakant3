import type { VacancyDict } from "../uz/vacancy";

const vacancy: Record<keyof VacancyDict, string> = {
  // ── Card / detail UI ───────────────────────────────────────────────────────
  "vacancy.fallbackTitle": "Vacancy",
  "vacancy.hidden": "Hidden",
  "vacancy.open": "View details",
  "vacancy.openPro": "View details (Pro)",
  "vacancy.save": "Save",
  "vacancy.saved": "Saved",
  "vacancy.noRegion": "Region not specified",
  "vacancy.description": "Description",
  "vacancy.contacts": "Contacts",
  "vacancy.lockedTitle": "Contact details are hidden",
  "vacancy.lockedHint": "Invite 5 friends or upgrade to Pro",
  "vacancy.openInBot": "Open in the bot",
  "vacancy.goPro": "Upgrade to Pro",
  "vacancy.opening": "Opening...",
  "vacancy.unknownCode": "Code {code}",
  "vacancy.openOriginal": "Original posting",
  "vacancy.openOn": "Open on {site}",
  "vacancy.source": "Source: {site}",

  // ── Detail rows ────────────────────────────────────────────────────────────
  "vacancy.row.address": "Address",
  "vacancy.row.district": "District/city",
  "vacancy.row.region": "Region",
  "vacancy.row.workType": "Work type",
  "vacancy.row.busyness": "Employment",
  "vacancy.row.payment": "Payment type",
  "vacancy.row.experience": "Experience",
  "vacancy.row.education": "Education",
  "vacancy.row.gender": "Gender",
  "vacancy.row.age": "Age",
  "vacancy.row.workingHours": "Working hours",
  "vacancy.row.count": "Open positions",
  "vacancy.row.deadline": "Deadline",
  "vacancy.row.postedAt": "Published",

  // ── Salary ─────────────────────────────────────────────────────────────────
  "vacancy.salary.negotiable": "Negotiable",
  "vacancy.salary.range": "{min} – {max} UZS",
  "vacancy.salary.from": "from {min} UZS",

  // ── Code maps ──────────────────────────────────────────────────────────────
  "vacancy.gender.1": "Male",
  "vacancy.gender.2": "Female",
  "vacancy.gender.3": "Any",

  "vacancy.work_type.1": "Permanent",
  "vacancy.work_type.2": "Temporary",
  "vacancy.work_type.3": "Seasonal",

  "vacancy.busyness.1": "Full-time",
  "vacancy.busyness.2": "Part-time",

  "vacancy.payment.1": "Monthly",
  "vacancy.payment.2": "Daily",
  "vacancy.payment.3": "Hourly",
  "vacancy.payment.4": "Piecework",

  "vacancy.education.1": "Secondary",
  "vacancy.education.2": "Vocational",
  "vacancy.education.3": "Bachelor's",
  "vacancy.education.4": "Master's",

  "vacancy.experience.1": "No experience required",
  "vacancy.experience.2": "Up to 1 year",
  "vacancy.experience.3": "1–3 years",
  "vacancy.experience.4": "3+ years",

  // ── hh.uz dictionary ids (source: src/functions/vacancy_format.py _HH_FIELDS) ──
  "vacancy.hh.experience.noExperience": "No experience",
  "vacancy.hh.experience.between1And3": "1–3 years",
  "vacancy.hh.experience.between3And6": "3–6 years",
  "vacancy.hh.experience.moreThan6": "Over 6 years",
  "vacancy.hh.employment.full": "Full-time",
  "vacancy.hh.employment.part": "Part-time",
  "vacancy.hh.employment.project": "Project work",
  "vacancy.hh.employment.volunteer": "Volunteering",
  "vacancy.hh.employment.probation": "Internship",
  "vacancy.hh.schedule.fullDay": "Full day",
  "vacancy.hh.schedule.shift": "Shift work",
  "vacancy.hh.schedule.flexible": "Flexible schedule",
  "vacancy.hh.schedule.remote": "Remote work",
  "vacancy.hh.schedule.flyInFlyOut": "Rotation (fly-in/fly-out)",
};

export default vacancy;
