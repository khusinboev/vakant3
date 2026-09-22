# Admin UI v3 — ixcham, mobil-birinchi qayta dizayn (spetsifikatsiya)

Tuzilgan: 2026-09-22. Bu hujjat foydalanuvchi topshirig'ining qayta yozilgan, o'lchanadigan shakli. Har bir agent shu hujjatga qarab ishlaydi; "chiroyli bo'lsin" degan gap yo'q, faqat tekshirsa bo'ladigan qoidalar bor.

## 0. Muammo bayoni (nima uchun)
Admin panel Telegram Mini App ichida ishlaydi: odatiy ekran 360–430px kenglik, 700–800px balandlik, ustida Telegram sarlavhasi, pastida tizim indikatorlari. Hozirgi v2 UI desktop mantig'ida yozilgan: matnlar `text-sm/base`, kartalar `p-4 rounded-2xl` ichma-ich, filtrlar 3–5 qatorga yoyiladi, ikki pastki panel (app BottomNav + admin tabs) 110px joy oladi, ko'p sub-holatlar (drawer, sheet, tab, editor) URL'da yo'q, shuning uchun telefonning "back" tugmasi va noutbukdagi ikki barmoqli surish (brauzer history back) ularni yopmaydi, balki paneldan chiqib ketadi.

O'lchangan holat (audit, 390×780): ilova sarlavhasi 53px + admin sarlavhasi 69px + admin tablari 44px + ilova BottomNav 55px + safe-area ≈ **245px chrome (31%)**, fullscreen'da ≈ 300px (38%); pastki padding ikki marta (144px) qo'yilgan; Users filtrlari ~240px (5 qator); mobil karta qatori ~95px (ekranda 5 ta); KPI 2×2 bloki ~190px; 72 joyda 9–11px matn; overlay'lardan hech biri history'da emas (back tugmasi sheet'ni yopmaydi, sahifadan chiqib ketadi); 12 sahifadan 4 tasi tab bar'da.

Maqsad: bir qo'l bilan, kichik ekranda, minimal scroll bilan boshqariladigan, har qadamda "orqaga" ishlaydigan, zich lekin o'qiladigan panel.

## 1. Asosiy tamoyillar (tekshiriladigan)
1. **Har holat = history yozuvi.** Sahifa, sub-tab, drawer, sheet, editor, tasdiq dialogi — barchasi URL yoki `history.state` orqali ifodalanadi. Telegram BackButton, brauzer back (ikki barmoq surish / Alt+←), `Esc` va sarlavhadagi ‹ tugmasi hammasi `history.back()` chaqiradi. Bitta "back" bitta darajani yopadi. Panelning ildizida back → ilovaning `/app` sahifasiga.
2. **Bitta sarlavha, bitta pastki panel.** Admin `/admin/*` ilova `Layout`isiz render bo'ladi: ilova sarlavhasi va BottomNav yo'q; admin sarlavhasi 40px (‹ | sarlavha | asosiy amal/⋯), til/tema tugmalari sarlavhadan olib tashlanadi (Settings ichida). Pastda 44px admin bar (4 element: Bosh, Foydalanuvchilar, Xabar, Ko'proq). "Ko'proq" — ikonkali to'r sheet, barcha bo'limlar rol bo'yicha. Klaviatura ochilganda bar yashirinmaydi, faqat `--bottom-safe` bilan siljiydi (layout sakrashi yo'q).
2b. **Telegram MainButton va Haptic.** Telegram ichida (mobil) ekranning yagona asosiy amali `WebApp.MainButton` orqali ko'rsatiladi (Saqlash / Navbatga qo'yish / Qo'shish / Yuborish), `showProgress` bilan; sahifada qo'shimcha ActionBar chizilmaydi. Telegram tashqarisida yoki desktop'da MainButton bo'lmasa in-page `ActionBar` fallback. Tasdiq va xato holatlarida `HapticFeedback.notificationOccurred`. `useMainButton({text, onClick, enabled, loading})` hook.
3. **Chrome ≤ 96px.** Sarlavha (40px) + pastki bar (44px) + safe-area. Filtr, tab, statistika kartalari kontent oqimida (scroll bilan ketadi), sticky emas; faqat asosiy amal tugmasi (agar bo'lsa) pastki barning ustida sticky.
4. **Zichlik shkalasi (o'qiladigan pastki chegara bilan):** admin ildiz elementida `text-[13px] leading-snug`; ikkilamchi matn `text-[11px]` — **11px dan kichik matn taqiqlanadi** (`text-[9px]`, `text-[10px]` yo'q); sarlavha `text-[15px] font-semibold`; raqamlar `tabular-nums`. Qator balandligi 40px (jadval) / 56px (ikki qatorli karta). Tugma balandligi 32px (`h-8`), ikonkali tugma 32×32, asosiy amal 40px. Padding: karta `p-3`, `rounded-xl`, kartalar ichma-ich emas (maksimal 1 daraja). Bo'shliq `gap-2`/`space-y-2`.
5. **Yashiriluvchi hamma narsa:** filtrlar — chip qatori (faol filtrlar) + "Filtrlar" tugmasi → sheet; uzun formalar — bo'limlar `Accordion` (bitta ochiq), ikkilamchi parametrlar "Qo'shimcha" ostida yig'ilgan; jadval ustunlari — mobil kartada 2 qator: sarlavha + 2–3 meta; statistika — 2×2 kichik tile, 3-4 raqam bir qatorda.
6. **Bir asosiy amal.** Har ekranda bitta aniq asosiy tugma (pastda sticky yoki sarlavhaning o'ng burchagida). Qolgan amallar "⋯" menyu-sheet ichida. Xavfli amallar qizil, tasdiq dialogi bilan (server confirm-token oqimi saqlanadi).
7. **Desktop rejimi (≥1024px):** sidebar 56px rail (ikonka + tooltip), hover'da 220px ga kengayadi yoki ⌘/Ctrl+B bilan qotiriladi; kontent max 1100px; jadvallar to'liq; drawer o'ngdan 420px; klaviatura: `Esc` back, `/` qidiruv fokus, `g u`/`g b` kabi tez o'tish shart emas (keyinroq).
8. **Ishlash:** birinchi paint chrome + skeleton ≤ 100ms; recharts faqat grafik ko'rinadigan bo'limda lazy; ro'yxatlar cursor bilan "Yana yuklash".
9. **A11y saqlanadi:** touch target ≥ 32px (44px bo'lmasa ham, oraliq ≥ 8px), kontrast 4.5:1, `role`/`aria-*` avvalgidek, fokus halqasi ko'rinadi.
10. **Hech narsa yo'qolmaydi:** v2 dagi barcha funksiyalar (8 sahifa + Overview/Settings) saqlanadi; faqat joylashuv va zichlik o'zgaradi.

## 2. Navigatsiya modeli
Marshrutlar (React Router, `/admin/*`):
```
/admin                      → dashboard (Overview + analytics tiles)
/admin/users                → ro'yxat
/admin/users/:id            → detal (mobil: to'liq ekran sahifa; desktop: o'ng drawer) 
/admin/users/:id/action/:k  → amal sheet'i (pro|balance|ban|message) — history yozuvi
/admin/broadcasts, /admin/broadcasts/new, /admin/broadcasts/:id
/admin/channels
/admin/content, /admin/content/:kind (articles|tips|categories), /admin/content/:kind/:id (editor), /new
/admin/finance?tab=summary|transactions|referrals
/admin/autopost
/admin/system?tab=health|admins|audit|errors
/admin/settings?section=autopost|referral|pricing|resume
/admin/more                 → bo'limlar to'ri (mobil)
```
Qoidalar:
- Sheet/dialog ochilganda `navigate(location, {state: {sheet: "<name>"}})` (push). Yopish = `history.back()`. Sheet komponenti `location.state.sheet` ga qaraydi; sahifa yangilansa (refresh) sheet ochiq bo'lmaydi — bu normal.
- `useAdminBack()` hook: Telegram BackButton'ni admin ichida DOIM ko'rsatadi (ildizda ham: u `/app` ga qaytaradi), bosilganda: ochiq sheet/dialog bo'lsa yopadi (history.back), aks holda `navigate(-1)`; agar history bo'sh bo'lsa `/app`.
- `Esc` tugmasi = xuddi shu. Sarlavhadagi ‹ tugmasi = xuddi shu (desktop'da ham ko'rinadi).
- Filtr/sub-tab holati URL query'da (`?q=&pro=1&tab=audit`), shuning uchun back filtrni ham "bekor qiladi" (bir qadam).
- `useBackInterceptor` (mavjud) faqat maxsus holatlar uchun (masalan, saqlanmagan editor: "O'zgarishlar saqlanmagan, chiqasizmi?" dialogi).

## 3. Komponent kutubxonasi (v3, `src/pages/Admin/ui/`)
Barchasi zichlik shkalasiga mos, tokenlar bilan, dark mode, a11y.
- `AdminShell` — sarlavha (‹ | sarlavha | asosiy amal/⋯) + kontent + `AdminBar` (mobil) / `Rail` (desktop). Ilovaning Layout/BottomNav'ini admin ichida o'chiradi (App.tsx darajasida `/admin/*` Layout'siz).
- `AdminBar` — 4 element, faol holat, badge (masalan ishlayotgan broadcast soni).
- `MoreSheet` — bo'limlar to'ri (3 ustun), rol bo'yicha, tez amallar (Post now, Yangi xabar).
- `Sheet` — pastdan (mobil) / markazdan (desktop) modal, history bilan integratsiya, `size: auto|full`, sarlavha + yopish, ichida scroll.
- `Accordion` / `Section` — sarlavha qatori (title + summary + chevron), bitta ochiq (yoki `multiple`), holat URL'da ixtiyoriy.
- `FilterChips` + `FilterSheet` — faol filtrlar chip (× bilan olib tashlash), "Filtrlar (n)" tugmasi sheet ochadi; sheet ichida guruhlangan select/toggle/date; "Qo'llash"/"Tozalash"; URL query'ga yoziladi.
- `SearchBar` — 36px, ikonka, debounce, tozalash ×; mobil sarlavha ostida.
- `List`/`ListRow` — zich qator: chap ikonka/avatar 28px, sarlavha 13px, meta 11px, o'ngda qiymat/chip/chevron; bosilsa navigate.
- `DataTable` (desktop) — 40px qator, sticky sarlavha, ustun tanlash sheet'i (mobil uchun kerak emas).
- `StatTile` — 2×2 to'r, 64px balandlik, raqam 18px, yorliq 11px, delta chip.
- `Chip`, `Badge`, `StatusDot`, `ProgressBar` (thin 4px), `KeyValue` (2 ustunli zich ro'yxat), `Toolbar` (tugmalar guruhi, overflow → ⋯), `IconButton` (32px, `aria-label`, desktop tooltip), `ActionBar` (sticky pastki, 1 asosiy + 1 ikkilamchi), `SegmentedControl` (kichik, 28px), `Tabs` (scrollable, 32px, URL'ga bog'liq), `JsonDetails` (mavjud, zich), `EmptyState` (ixcham, 96px), `Skeleton`.
- `useHistorySheet(name)` → `{open, openSheet(), close()}`; `useQueryState(key, default)` → URL query bilan bog'langan state; `useAdminBack()`; `useIsDesktop()`; `useMainButton(...)`; `Button` primitivi (`size: sm|md`, `variant: primary|secondary|ghost|danger`, 32/40px) — admin ichida boshqa tugma uslubi ishlatilmaydi; `Skeleton` primitivi (inline `animate-pulse` yo'q).

## 4. Sahifalar bo'yicha talablar
- **Dashboard:** 2×2 StatTile (bugun: yangi, faol, Pro, daromad) + "So'nggi 7 kun" mini-chart (sparkline, recharts'siz — SVG) + tez amallar qatori (Post now, Yangi xabar, Kanal qo'shish) + "Tizim holati" bir qatorli status (yashil/qizil) → System'ga havola. Resume KPI donutlari Accordion ostida.
- **Users:** SearchBar + FilterChips; List (avatar, ism/@username, meta: id · Pro/Free · balans · oxirgi faollik); detal alohida sahifa: sarlavha (ism, rol chiplari), KeyValue, Accordion: Hamyon / Referal / Resume / Bildirishnoma / Saqlanganlar (lazy); ActionBar: "Amallar ⋯" sheet (Pro, Balans, Ban, Xabar, Reset), har biri o'z sheet'i (history).
- **Broadcasts:** List (status dot, sarlavha/matn boshi, progress thin bar, sent/total); FAB-o'rnida ActionBar "Yangi xabar"; Composer alohida sahifa, Accordion: Matn (toolbar ixcham 5 ikonka) / Media / Tugmalar / Auditoriya; pastda ActionBar: "Test yuborish" (ikkilamchi) + "Navbatga qo'yish" (asosiy, tasdiq); detal sahifa: counters 4 tile + xatolar ro'yxati + Cancel (⋯).
- **Channels:** List + "Qo'shish" ActionBar → sheet (havola input, natija inline); qator ⋯: tekshirish/o'chirish/yoqish.
- **Content:** Tabs (Maqolalar/Maslahatlar/Kategoriyalar) URL'da; List; editor alohida sahifa: sarlavha qatori (slug, published toggle), til `SegmentedControl` (uz/ru/en), maydonlar Accordion (Sarlavha+Qisqacha / Matn / Manba), toolbar 5 ikonka, hisoblagich; ActionBar: Saqlash; saqlanmagan → back interceptor dialog.
- **Finance:** Tabs URL'da; Summary: `SegmentedControl` davr + 2×2 tile + bitta grafik (lazy); Transactions: FilterChips + List; Referrals: List.
- **AutoPost:** status KeyValue (ixcham) + "Post now" ActionBar + bugungi slotlar (chip qatori) + tarix List (status dot).
- **System:** Tabs URL'da; Health KeyValue + status dot'lar; Admins List + "Qo'shish" sheet; Audit/Errors List + FilterChips, qator bosilsa JsonDetails sheet.
- **Settings:** Accordion bo'limlari (Auto-post / Referal / Narxlar / Resume KPI), har maydon `InlineEditRow` zich (label chap, qiymat o'ng, bosilsa inline input), saqlash avtomatik (blur) + toast; version conflict → toast + qayta yuklash.

## 4b. Audit'dan kelib chiqqan majburiy o'zgarishlar (sahifalar bo'yicha)
- Users: 8 ta filtr boshqaruvi (4–5 qator) → SearchBar + FilterChips + FilterSheet; detal `/admin/users/:id` sahifa; `views/QuickActionsView` va `tabs/UsersTab` o'chiriladi (Users detal amallari bilan 1:1 takror).
- Finance: 5 StatCard + grafik + 4 filtr jadvaldan oldin → 2×2 StatTile (davr SegmentedControl sarlavha ostida), grafik Accordion ostida, filtrlar chip+sheet; "karta ichida karta" yo'q; CSV eksport ⋯ menyuda.
- Channels: h1 + subtitle + GateInfoCard + doimiy ochiq forma → ro'yxat birinchi, "Qo'shish" MainButton/ActionBar → sheet; gate izohi `Accordion` (yopiq).
- System/Admins: qo'shish formasi yopiq (sheet), sub-tablar URL'da (mavjud) — boshqa sahifalar ham shu uslubga o'tadi.
- Content: sub-tablar URL'da; editor `/admin/content/:kind/:id`; ichma-ich kartalar tekislanadi; saqlash MainButton; dirty-guard back interceptor bilan.
- Broadcasts: "compose" sub-tab → `/admin/broadcasts/new` sahifa; detal `/admin/broadcasts/:id`; Composer Accordion (Matn/Media/Tugmalar/Auditoriya), MainButton "Navbatga qo'yish", "Test" ⋯ da.
- AutoPost: 4 ta GroupCard ichida DataTable (ikki qavat karta) → yalang'och List; status KeyValue; Post now MainButton.
- Analytics/Overview: 9 StatCard (`p-3.5`) → 3 ustunli StatTile; 4 ta 268px grafik → Accordion ostida, bittadan; Overview KpiDonut 2×2 + 3 stat → bitta qatorli 4 meter; Resume KPI Accordion.
- Settings: 14 maydon, 4 GroupCard → Accordion (birinchisi ochiq), InlineEditRow zich (40px).
- Umumiy: `StatusChip` (7 nusxa → 1), `PeriodSelector` (2 → 1, `SegmentedControl`), `SubTabStrip` (4 → `Tabs`), `KeyValue` (5 → 1), `ProgressBar` (3 → 1), `PageHeader` h1'lar olib tashlanadi (sarlavha shell'da), `JsonDetails` hamma joyda qayta ishlatiladi.
- Matn: 72 ta 9–11px holat qayta ko'riladi: 9/10px → 11px, ikkilamchi 12px → 11px, asosiy 12px → 13px.

## 5. Bajarish rejasi (agentlar)
1. **UI-KIT agent (opus):** `src/pages/Admin/ui/*` komponentlari + hooklar + zichlik tokenlari (`admin-density` CSS class'lari `index.css` da) + Storybook'siz vizual smoke sahifa `/admin/_kit` (faqat dev). Shu bilan birga `AdminShell/AdminBar/MoreSheet/Rail` va navigatsiya (`useAdminBack`, history sheet), App.tsx'da `/admin/*` Layout'siz, `registry.ts` yangi marshrutlar.
2. **Sahifa agentlari (8, parallel, sonnet/opus):** har biri o'z sahifasini v3 kutubxonasiga ko'chiradi, faqat o'z papkasi + namespace. Funksiya yo'qotilmaydi.
3. **QA agent (opus):** avtomatik tekshiruvlar: `grep` bilan admin ichida `text-base|text-lg|p-4|p-5|rounded-2xl|h-10|h-11|h-12` yo'qligi (whitelist bilan), har sheet history bilan ochilishi (kod tahlili), har sahifada ‹ back; `tsc/lint/build`; bundle hajmi hisobot.
4. **Men:** integratsiya, build, commit, deploy, prod tekshiruv.

## 6. Qabul mezonlari
- 390×780 da har sahifaning birinchi ekranida: chrome ≤ 96px (hozir 245px), kamida 6 ta ma'lumot qatori (ro'yxat sahifalarida) yoki 2×2 tile + 1 bo'lim (dashboard) ko'rinadi.
- Admin ichidagi barcha `.tsx` fayllarda `text-base`, `text-lg`, `text-[9px]`, `text-[10px]`, `p-4`, `p-5`, `p-6`, `rounded-2xl`, `h-11`, `h-12`, `tap-target` ishlatilmaydi (istisno: dashboard tile raqami `text-lg`, bo'sh holat ikonkasi). Pastki padding faqat bitta joyda (`AdminShell`), qiymati bar balandligi + safe-area.
- Mobil ro'yxat qatori ≤ 56px (hozir ~95px), Users filtr bloki ≤ 44px (chip qatori) (hozir ~240px), KPI 2×2 bloki ≤ 140px (hozir ~190px).
- Har bir sheet/dialog/drawer `useHistorySheet` yoki marshrut orqali ochiladi; kodda `useState(false)` bilan boshqariladigan modal qolmaydi (QA grep).
- Telegram BackButton admin ichida hamma joyda ko'rinadi va bir daraja qaytaradi; `Esc` ham; desktop sarlavhada ‹ bor.
- `tsc`, `lint`, `build` toza; 8 sahifa + dashboard + settings funksiyalari v2 bilan bir xil (QA ro'yxati).
- Bundle: admin entry chunk ≤ 30 kB gz, har sahifa chunk ≤ 15 kB gz (Content/Broadcasts ≤ 20 kB).

## 7. Bajarilish holati (2026-09-22)
Bajarildi: 12 agent parallel (1 kit + 9 sahifa + QA + tozalash). Natija:

| Ko'rsatkich | v2 | v3 |
|---|---|---|
| Chrome (390×780) | 245px (31%) | 84px + safe-area |
| Sarlavha panellari | 2 ta (53 + 69px) | 1 ta (40px) |
| Pastki panellar | 2 ta (44 + 55px) | 1 ta (44px) |
| Ro'yxat qatori | ~95px | 40/56px |
| Users filtrlari | ~240px (5 qator) | chip qatori + sheet |
| 11px dan kichik matn | 72 joy | 0 |
| History'da bo'lmagan overlay | ~15 ta | 0 |
| Admin UI kodi | — | −3763 satr |

Navigatsiya: har holat (sahifa, sub-tab, filtr, sheet, editor, tasdiq) URL yoki `history.state` da. Telegram BackButton, brauzer back (ikki barmoq surish), `Esc` va sarlavhadagi ‹ — hammasi bir daraja qaytaradi (`useAdminBack`, `useHistorySheet`). Ildizda back → `/app`.

Telegram integratsiyasi: har ekranning yagona asosiy amali `WebApp.MainButton` ga ulanadi (`useMainButton`), tasdiq/xatoda `HapticFeedback`. Telegram tashqarisida `ActionBar` fallback.

Chunk hajmlari (gz): admin entry 8.0 kB, eng katta sahifa (broadcasts) 13.7 kB — byudjetdan past. recharts faqat ochilgan grafik akkordeonida yuklanadi.

Qolgan ochiq qarorlar: Content editor akkordeoni va til tanlovi lokal holatda (dirty-guard bilan ziddiyat xavfi tufayli ataylab); `AdminUserDetail.recent_events` maydoni endi ishlatilmaydi (resume inspect uni almashtirdi).
