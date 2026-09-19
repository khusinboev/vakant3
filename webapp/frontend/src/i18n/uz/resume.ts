/**
 * Resume namespace — the resume wizard (`src/pages/ResumeStudio/**`) and the
 * generic wizard UI primitives it promoted into `src/components/ui/`.
 * uz is the source language; ru/en are typed against these keys.
 */
const resume = {
  // ── Shell ──────────────────────────────────────────────────────────────────
  "resume.title": "Rezyume ustasi",
  "resume.preview": "Ko'rinish",
  "resume.previewTitle": "Rezyume ko'rinishi",
  "resume.previewLive": "Jonli ko'rinish",
  "resume.stepOf": "{step}/{total}",
  "resume.sync.idle": "Kutilmoqda",
  "resume.sync.saving": "Saqlanmoqda...",
  "resume.sync.synced": "Saqlandi",
  "resume.sync.error": "Xatolik",

  // ── Steps ──────────────────────────────────────────────────────────────────
  "resume.step.basic": "Asosiy",
  "resume.step.experience": "Tajriba",
  "resume.step.education": "Ta'lim",
  "resume.step.skills": "Ko'nikma",
  "resume.step.summary": "Summary",
  "resume.step.template": "Shablon",
  "resume.hint.basic": "Ism, lavozim va kontakt ma'lumotlari",
  "resume.hint.experience": "Ish tajriba va yutuqlaringizni kiriting",
  "resume.hint.education": "Ta'lim va malakangizni kiriting",
  "resume.hint.skills": "Ko'nikmalar va til bilimlaringizni kiriting",
  "resume.hint.summary": "Qisqacha professional tavsif yozing",
  "resume.hint.template": "Dizayn tanlang va rezyumeni tayyorlang",

  // ── Draft / conflict banners ───────────────────────────────────────────────
  "resume.serverDraft.text": "Serverda saqlangan yangiroq nusxa bor.",
  "resume.serverDraft.load": "Serverdan yuklash",
  "resume.serverDraft.loaded": "Ma'lumotlar serverdan yuklandi.",
  "resume.localDraft.restored": "Saqlanmagan qoralama tiklandi.",
  "resume.conflict.title": "Serverdagi nusxa yangilandi",
  "resume.conflict.body":
    "Rezyume boshqa qurilmada o'zgartirildi. Qaysi nusxani qoldiramiz?",
  "resume.conflict.reload": "Serverdagisini yuklash",
  "resume.conflict.keepMine": "Meniki qolsin",

  // ── Basic step ─────────────────────────────────────────────────────────────
  "resume.field.fullName": "F.I.Sh",
  "resume.field.position": "Lavozim",
  "resume.field.phone": "Telefon",
  "resume.field.email": "Email",
  "resume.field.location": "Manzil",
  "resume.field.website": "Portfolio / LinkedIn",
  "resume.ph.fullName": "Abdullayev Ali",
  "resume.ph.position": "Frontend dasturchi",
  "resume.ph.phone": "+998 90 123 45 67",
  "resume.ph.email": "ali@email.com",
  "resume.ph.location": "Toshkent, O'zbekiston",
  "resume.ph.website": "linkedin.com/in/username",

  // ── Experience step ────────────────────────────────────────────────────────
  "resume.exp.empty": "Ish tajribasi qo'shilmagan",
  "resume.exp.emptyHint": "Quyidagi tugmani bosib qo'shing",
  "resume.exp.add": "Tajriba qo'shish",
  "resume.exp.item": "Tajriba {n}",
  "resume.exp.remove": "Tajribani o'chirish",
  "resume.exp.role": "Lavozim",
  "resume.exp.company": "Kompaniya",
  "resume.exp.start": "Boshlanish",
  "resume.exp.end": "Tugash",
  "resume.exp.location": "Joylashuv",
  "resume.exp.description": "Natijalar va vazifalar",
  "resume.exp.roleFallback": "Lavozim",
  "resume.exp.companyFallback": "Kompaniya",
  "resume.ph.role": "Senior dasturchi",
  "resume.ph.company": "Google Inc.",
  "resume.ph.expLocation": "Toshkent",
  "resume.ph.expDescription": "- Asosiy yutuqlar va vazifalar...",

  // ── Experience suggestions ─────────────────────────────────────────────────
  "resume.suggest.dev1": "Asosiy jarayonlarni optimallashtirib, javob vaqtini 30% ga kamaytirdim.",
  "resume.suggest.dev2":
    "Avtomatlashtirilgan testlarni joriy etib, ishlab chiqarishdagi xatolarni 20% ga kamaytirdim.",
  "resume.suggest.dev3":
    "Jamoa bilan birgalikda kundalik foydalaniladigan asosiy funksiyani ishga tushirdim.",
  "resume.suggest.sales1": "Choraklik savdo maqsadlarini 18% ga oshirib bajardim.",
  "resume.suggest.sales2":
    "Mijozlar bilan munosabatlarni mustahkamlab, ularni ushlab qolishni 15% ga oshirdim.",
  "resume.suggest.sales3": "Jamoa a'zolarini o'qitib, bitim yopish ko'rsatkichini yaxshiladim.",
  "resume.suggest.design1":
    "Foydalanuvchi tajribasini tahlil qilib, konversiyani 25% ga oshirdim.",
  "resume.suggest.design2":
    "Mobil va web platformalar uchun moslashuvchan interfeys prototiplarini ishlab chiqdim.",
  "resume.suggest.design3":
    "Foydalanuvchi intervyu va testlari asosida mahsulot dizaynini yaxshiladim.",
  "resume.suggest.generic1":
    "Jamoa ish jarayonlarini takomillashtirib, o'lchanadigan natijalarga erishdim.",
  "resume.suggest.generic2":
    "Manfaatdor tomonlar bilan hamkorlikda muhim loyihalarni o'z vaqtida topshirdim.",
  "resume.suggest.generic3": "KPI ko'rsatkichlarini kuzatib, ish sifatini izchil yaxshiladim.",

  // ── Education step ─────────────────────────────────────────────────────────
  "resume.edu.empty": "Ta'lim ma'lumoti qo'shilmagan",
  "resume.edu.emptyHint": "Quyidagi tugmani bosib qo'shing",
  "resume.edu.add": "Ta'lim qo'shish",
  "resume.edu.item": "Ta'lim {n}",
  "resume.edu.remove": "Ta'limni o'chirish",
  "resume.edu.school": "O'quv yurti",
  "resume.edu.degree": "Daraja",
  "resume.edu.start": "Boshlanish",
  "resume.edu.end": "Tugash",
  "resume.edu.description": "Qo'shimcha ma'lumot",
  "resume.edu.schoolFallback": "O'quv yurti",
  "resume.edu.degreeFallback": "Daraja",
  "resume.edu.selectDegree": "Daraja tanlang",
  "resume.ph.school": "Toshkent davlat texnika universiteti",
  "resume.ph.eduDescription": "Diplom, mukofotlar, loyihalar...",
  "resume.degree.secondary": "O'rta ta'lim",
  "resume.degree.vocational": "O'rta maxsus ta'lim (kollej / texnikum)",
  "resume.degree.bachelor": "Bakalavr",
  "resume.degree.master": "Magistr",
  "resume.degree.phd": "Doktorantura (PhD)",
  "resume.degree.courses": "Sertifikat / Kurslar",
  "resume.degree.other": "Boshqa",

  // ── Skills step ────────────────────────────────────────────────────────────
  "resume.skills.label": "Ko'nikmalar",
  "resume.skills.hint": "— Enter yoki vergul bilan ajrating",
  "resume.skills.count": "{n} ta ko'nikma",
  "resume.skills.min": "(kamida {n} ta)",
  "resume.skills.suggestTitle": "«{position}» uchun tavsiyalar",
  "resume.languages.label": "Tillar",
  "resume.ph.skills": "JavaScript, React, Python...",
  "resume.ph.languages": "O'zbek, Ingliz, Rus...",

  // ── Summary step ───────────────────────────────────────────────────────────
  "resume.summary.label": "Professional summary",
  "resume.summary.minHint": "Kamida {n} ta belgi",
  "resume.summary.charCount": "{n} belgi",
  "resume.ph.summary": "5+ yillik tajribaga ega dasturchi sifatida...",
  "resume.match.title": "Vakansiya bo'yicha moslash",
  "resume.match.subtitle": "Vakansiya matnini kiriting — kalit so'zlarni tavsiya qilamiz",
  "resume.ph.jobDescription": "Ish e'loni matnini shu yerga nusxalang...",
  "resume.match.topKeywords": "Top kalit so'zlar:",
  "resume.match.missing": "Rezyumeda yo'q kalit so'zlar:",
  "resume.match.allPresent": "Barcha kalit so'zlar rezyumeda mavjud!",

  // ── Template step ──────────────────────────────────────────────────────────
  "resume.tpl.section": "Shablon",
  "resume.tpl.change": "O'zgartirish",
  "resume.tpl.sheetTitle": "Shablon tanlash",
  "resume.tpl.accent": "Accent rang",
  "resume.tpl.done": "Tayyor",
  "resume.tpl.badgePhoto": "RASM",
  "resume.tpl.badgeSidebar": "PANEL",
  "resume.tpl.badgeMono": "MONO",
  "resume.tpl.badgeDark": "TO'Q",
  "resume.tpl.badgeColor": "rang",
  "resume.tpl.badgePro": "PRO",
  "resume.tpl.pick": "{title} shablonini tanlash",

  // ── Template catalogue (fallback when the API list is unavailable) ─────────
  "resume.tplTitle.clean": "Clean Classic",
  "resume.tplDesc.clean": "Sodda klassik ko'rinish, barcha sohalar uchun.",
  "resume.tplTitle.modern": "Modern Accent",
  "resume.tplDesc.modern": "Qisqa va zamonaviy blokli uslub.",
  "resume.tplTitle.compact": "Compact One-Page",
  "resume.tplDesc.compact": "Bir sahifaga sig'adigan ixcham format.",
  "resume.tplTitle.executive": "Executive Dark",
  "resume.tplDesc.executive": "Korporativ uslub: to'q sarlavha va ikki ustunli ko'nikmalar.",
  "resume.tplTitle.timeline": "Timeline Classic",
  "resume.tplDesc.timeline": "Tajriba bo'ylab vertikal chiziq va doira belgilari bilan vaqt o'qi.",
  "resume.tplTitle.minimal": "Minimal Pure",
  "resume.tplDesc.minimal": "Faqat tipografiya, rangli bloklarsiz sof professional ko'rinish.",
  "resume.tplTitle.creative": "Creative Stripe",
  "resume.tplDesc.creative": "Chap tomonda qalin rang zolagi — kreativ sohalar uchun.",
  "resume.tplTitle.photo_classic": "Photo Classic",
  "resume.tplDesc.photo_classic": "Sarlavhaning o'ng qismida profil rasmi bo'lgan klassik uslub.",
  "resume.tplTitle.photo_sidebar": "Photo Sidebar",
  "resume.tplDesc.photo_sidebar": "Keng yon panel: yuqorida rasm, asosiy maydonda tajriba va ta'lim.",
  "resume.tplTitle.europass": "Europass Grid",
  "resume.tplDesc.europass": "Europass uslubida ikki ustunli jadval va ixtiyoriy rasm.",
  "resume.tplTitle.infographic": "Infographic Visual",
  "resume.tplDesc.infographic": "Vizual ko'nikma panellari, rangli bo'limlar va accent belgilari.",

  // ── Photo ──────────────────────────────────────────────────────────────────
  "resume.photo.title": "Profil rasmi",
  "resume.photo.alt": "Profil rasmi",
  "resume.photo.included": "Rasm PDF ga kiritiladi",
  "resume.photo.replace": "Almashtirish",
  "resume.photo.remove": "O'chirish",
  "resume.photo.pick": "Rasm tanlash",
  "resume.photo.uploading": "Yuklanmoqda...",
  "resume.photo.formats": "JPEG · PNG · WEBP",
  "resume.photo.error": "Rasmni yuklab bo'lmadi. Boshqa fayl tanlang.",

  // ── Actions / toasts ───────────────────────────────────────────────────────
  "resume.action.back": "Orqaga",
  "resume.action.next": "Keyingi",
  "resume.action.save": "Saqlash",
  "resume.action.saved": "Saqlandi",
  "resume.action.saving": "Saqlanmoqda",
  "resume.send.title": "Yuborish",
  "resume.send.button": "Telegramga yuborish",
  "resume.send.short": "Yuborish",
  "resume.send.sending": "Yuborilmoqda...",
  "resume.toast.saved": "Ma'lumotlar saqlandi.",
  "resume.toast.sent": "Rezyume Telegramga yuborildi.",

  // ── Validation ─────────────────────────────────────────────────────────────
  "resume.err.fullName": "F.I.Sh majburiy",
  "resume.err.position": "Lavozim majburiy",
  "resume.err.contact": "Kamida email yoki telefon kiriting",
  "resume.err.experienceRequired": "Kamida bitta ish tajribasi kiriting",
  "resume.err.experienceFields": "Har bir tajribada lavozim va kompaniya kiriting",
  "resume.err.educationRequired": "Kamida bitta ta'lim yozuvi kiriting",
  "resume.err.skillsMin": "Kamida {n} ta ko'nikma kiriting",
  "resume.err.summaryMin": "Summary kamida {n} ta belgidan iborat bo'lsin",
  "resume.err.templateRequired": "Shablon tanlang",

  // ── Premium upsell ─────────────────────────────────────────────────────────
  "resume.premium.title": "Bu shablon Pro tarif uchun",
  "resume.premium.body":
    "Do'stlaringizni taklif qiling yoki hisobingizni to'ldirib Pro tarifga o'ting.",
  "resume.premium.perk1": "{n} ta premium shablon",
  "resume.premium.perk2": "Cheksiz saqlash",
  "resume.premium.perk3": "Barcha vakansiya kontaktlari",
  "resume.premium.toWallet": "Hamyonga o'tish",

  // ── Live preview card ──────────────────────────────────────────────────────
  "resume.card.unnamed": "Nomsiz nomzod",
  "resume.card.noPosition": "Lavozim ko'rsatilmagan",
  "resume.card.noContact": "Kontakt kiritilmagan",
  "resume.card.summary": "Summary",
  "resume.card.experience": "Tajriba",
  "resume.card.skills": "Ko'nikmalar",

  // ── Date picker (src/components/ui/MonthYearPicker.tsx) ────────────────────
  "resume.date.placeholder": "Oy / Yil",
  "resume.date.sheetTitle": "Sana tanlash",
  "resume.date.month": "Oy",
  "resume.date.year": "Yil",
  "resume.date.present": "Hozir (davom etmoqda)",
  "resume.date.presentShort": "Hozir",
  "resume.date.clear": "Tozalash",

  // ── Tag input (src/components/ui/TagInput.tsx) ─────────────────────────────
  "resume.tag.add": "+qo'shish",
  "resume.tag.remove": "{tag} ni o'chirish",
};

export type ResumeDict = typeof resume;
export default resume;
