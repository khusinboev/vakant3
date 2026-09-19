# Vakant3 — To'liq Loyiha Yo'l Xaritasi
> Tuzilgan: 2026-05-30 | Versiya: 1.0

---

## Loyiha holati (hozir mavjud)

| Modul | Holat |
|-------|-------|
| Bot: start, referral deeplink, admin panel | ✅ |
| WebApp: ish qidirish, filter, infinite scroll | ✅ |
| WebApp: saqlangan ishlar | ✅ |
| WebApp: profil, hamyon, referral | ✅ |
| WebApp: Resume Studio (6 bosqich, 11 shablon, PDF) | ✅ |
| WebApp: Admin panel (sozlamalar, metrics) | ✅ |
| Auto-post: kuniga 1 ta, 1 marta, random vaqt | ✅ |
| Referral tizim (reward, balans, Pro aktivlashtirish) | ✅ |
| Pro-lock: maosh chegarasi asosida vakansiya blokash | ✅ |

---

## Yangi funksiyalar (5 Sprint)

---

## SPRINT 1 — Kontent Hub (Qonunchilik + HR)
**Taxminiy hajm:** ~600 satr | **Boshlash:** birinchi

### 1.1 Ma'lumot fayllari (statik)

**Yangi fayl:** `src/data/law_articles.py`

```python
ARTICLES = [
  {
    "id": "mehnat-worktime",
    "category": "Ish vaqti",
    "title": "Kunlik va haftalik ish vaqti me'yori",
    "summary": "Haftalik 40 soat, kuniga 8 soat. Qisqartirilgan ish vaqtlari...",
    "full_text": "...(to'liq matn, max 4000 belgi)...",
    "source_url": "https://lex.uz/docs/...",
    "source_label": "Mehnat Kodeksi, 116-modda"
  },
  # Jami 12 ta maqola:
  # 1. Kunlik/haftalik ish vaqti (116-modda)
  # 2. Yillik ta'til muddati (134, 136-moddalar)
  # 3. Ortiqcha ish vaqti va haq to'lash (120, 157)
  # 4. Kasallik varaqasi to'lash tartibi (280-281)
  # 5. Mehnat shartnomasi tuzish qoidalari (74-77)
  # 6. Sinov muddati qoidalari (84-modda)
  # 7. Ishdan bo'shatish asoslari (100-104)
  # 8. Eng kam ish haqi (MROT 2025 - Hukumat qarori)
  # 9. Homilador ayollar kafolatlari (225-226)
  # 10. Ish haqi kechiktirilganda javobgarlik (164)
  # 11. Dam olish kunlari va bayramlar (146-149)
  # 12. Mehnat nizolarini hal qilish (271-275)
]
```

**Yangi fayl:** `src/data/hr_tips.py`

```python
HR_TIPS = [
  {
    "id": "cv-mistakes",
    "title": "CV yozishda 5 ta eng ko'p uchraydigan xato",
    "text": "...(to'liq matn)..."
  },
  {
    "id": "interview-prep",
    "title": "Intervyuga tayyorlanish: 10 ta savol va javob",
    "text": "..."
  },
  # Hozicha 2-3 ta (sinov uchun), keyin ko'paytiriladi
]
```

### 1.2 FastAPI endpoint (WebApp uchun)

**Yangi router:** `webapp/routers/content.py`

```
GET /content/laws              → barcha maqolalar ro'yxati (id, category, title, summary)
GET /content/laws/{article_id} → bitta maqola to'liq (full_text, source_url, ...)
```

Auth shart emas — ochiq endpoint. Rate limit: slowapi 30/min.

### 1.3 WebApp sahifasi

**Yangi fayl:** `webapp/frontend/src/pages/Laws.tsx`

```
URL: /hub/laws

UI:
┌─────────────────────────────────┐
│ ⚖️ Qonunchilik                  │
│ O'zbekiston mehnat qonunchiligi │
├─────────────────────────────────┤
│ [Ish vaqti] [Ta'til] [Maosh]   │  ← kategoriya filter chips
├─────────────────────────────────┤
│ ┌───────────────────────────┐   │
│ │ 🕐 Ish vaqti              │   │
│ │ Kunlik va haftalik me'yor │   │
│ │ Haftalik 40 soat...       │   │
│ │                [Ko'rish →]│   │
│ └───────────────────────────┘   │
│ (qolgan kartochkalar...)        │
└─────────────────────────────────┘
```

**Ichki ko'rinish** (detail modal yoki sahifa):
```
⚖️ Kunlik va haftalik ish vaqti me'yori

Mehnat Kodeksi, 116-modda

[To'liq matn]

───────────────
📄 Asl hujjatga o'tish → lex.uz
```

**Yangi fayl:** `webapp/frontend/src/pages/LawDetail.tsx` yoki modal ichida ko'rsatiladi.

### 1.4 Hub sahifasi kengaytirish

**O'zgartiriladi:** `webapp/frontend/src/pages/Hub.tsx`

Hozirgi: faqat Resume Studio kartochkasi  
Yangi:
```
┌─────────────────────────────┐
│ 📄 Resume Studio            │  (mavjud)
│ [Ochish →]                  │
├─────────────────────────────┤
│ ⚖️ Qonunchilik              │  ← YANGI
│ Mehnat qonunchiligi, 12 ta  │
│ maqola                      │
│ [Ko'rish →]                 │
└─────────────────────────────┘
```

HR Maslahatlar — faqat botda, Hub'da ko'rsatilmaydi.

### 1.5 App routing

**O'zgartiriladi:** `webapp/frontend/src/App.tsx`

```typescript
// Lazy import qo'shish:
const Laws = lazy(() => import("./pages/Laws"));

// Route qo'shish:
<Route path="/hub/laws" element={<Layout><Laws /></Layout>} />
```

### 1.6 Backend main.py

**O'zgartiriladi:** `webapp/main.py`

```python
from webapp.routers import content
app.include_router(content.router)
```

### 1.7 Bot tomoni

**O'zgartiriladi:** `src/handlers/start.py` — reply keyboard kengaytirish

```python
# Asosiy reply keyboard (hozirgi inline → reply keyboard ham qo'shiladi)
main_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("⚖️ Qonunchilik"), KeyboardButton("💡 HR Maslahatlar")],
    ],
    resize_keyboard=True,
    is_persistent=True
)
```

**Yangi fayl:** `src/handlers/content.py`

```python
# ⚖️ Qonunchilik handler
@router.message(F.text == "⚖️ Qonunchilik")
async def laws_handler(message: Message):
    # Inline keyboard: 12 ta sarlavha → tugmalar
    # callback_data: "law:{article_id}"

@router.callback_query(F.data.startswith("law:"))
async def law_detail_handler(call: CallbackQuery):
    article_id = call.data.split(":")[1]
    article = get_article_by_id(article_id)
    
    text = format_law_text(article)  # max 2500 belgi, kesilsa "..." + link
    await call.message.answer(text, disable_web_page_preview=False)

# 💡 HR Maslahatlar handler
@router.message(F.text == "💡 HR Maslahatlar")
async def hr_tips_handler(message: Message):
    # Inline keyboard: tip sarlavhalari
    
@router.callback_query(F.data.startswith("hr:"))
async def hr_tip_detail_handler(call: CallbackQuery):
    # Matnni yuboradi
```

**Bot xabar formati (Qonunchilik):**
```
⚖️ Kunlik va haftalik ish vaqti me'yori

📋 Mehnat Kodeksi, 116-modda
🗂 Ish vaqti

─────────────────
[Matn — max 2500 belgi. Agar uzun bo'lsa:
...davomini to'liq o'qish uchun quyidagi havolaga o'ting.]
─────────────────
📄 Asl manba: lex.uz → [havola]
```

---

## SPRINT 2 — Premium Enforcement
**Taxminiy hajm:** ~400 satr

### 2.1 Global Filter tizimi (MUHIM: boshqa hamma sprint'ga ta'sir qiladi)

**Konsept:** Foydalanuvchi birinchi marta bildirishnomani yoqmoqchi bo'lganda (yoki ixtiyoriy profildan) global filtrni o'rnatadi. Bu filtr:
- Bildirishnomalar uchun (qaysi ishlardan xabar keladi)
- Keyinchalik search default sifatida ham ishlatilishi mumkin

**DB sxema (yangi ustun):**
```sql
-- users jadvaliga qo'shiladi (migration orqali):
ALTER TABLE users ADD COLUMN pref_filters_json TEXT;
-- Qiymat misoli: {"region_soato":"17","specs":"spec:12","min_salary":2000000}
```

**WebApp (Profil sahifasiga qo'shiladi):**
```
Mening filtrlarim
┌─────────────────────────────┐
│ Hudud:    [Toshkent ▼]      │
│ Soha:     [IT ▼]            │  
│ Min maosh:[2,000,000 ▼]     │
│ [Saqlash]                   │
└─────────────────────────────┘
```

**Backend:** `PATCH /profile/filters` — filters_json saqlash

### 2.2 Resume Template Lock

**Backend o'zgarishi** (`webapp/routers/resume.py`):

```python
FREE_TEMPLATES = {"clean", "modern", "compact"}

# /resume/templates endpointida:
for tpl in templates:
    tpl["is_premium"] = tpl["id"] not in FREE_TEMPLATES

# /resume/save va /resume/generate endpointlarida:
if template_id not in FREE_TEMPLATES:
    # user pro emasligini tekshir
    if not user_is_pro:
        raise HTTPException(403, {"code": "PREMIUM_TEMPLATE", "template": template_id})
```

**Frontend o'zgarishi** (`webapp/frontend/src/pages/ResumeStudio.tsx`):

Template card ustida lock overlay:
```
Premium shablon tanlanganda (free user):
┌─────────────────────────────────────┐
│ 💎 Bu shablon Pro tarif uchun       │
│                                     │
│ 5 ta do'st taklif qiling yoki       │
│ 10,000 so'm to'lang                 │
│                                     │
│ [💳 Hamyonga o'tish]  [Yopish]      │
└─────────────────────────────────────┘
```

Template grid'da premium shablonlar:
- Free user: `🔒` badge + to'q overlay
- Pro user: normal ko'rinadi

### 2.3 Saves Limit (5 ta)

**Backend o'zgarishi** (`webapp/routers/saves.py`):

```python
FREE_SAVE_LIMIT = 5

# POST /saves/{uid} da:
if not is_pro:
    cursor = await db.execute(
        "SELECT COUNT(*) FROM saves WHERE user_id = ?", (user_id,)
    )
    count = (await cursor.fetchone())[0]
    if count >= FREE_SAVE_LIMIT:
        raise HTTPException(
            status_code=403,
            detail={"code": "SAVE_LIMIT_REACHED", "limit": FREE_SAVE_LIMIT, "current": count}
        )
```

**Frontend o'zgarishi** (`webapp/frontend/src/hooks/useSaves.ts` va `VacancyCard.tsx`):

403 + `SAVE_LIMIT_REACHED` → BottomSheet modal:
```
📌 Saqlangan ishlar limiti (5/5)
Pro tarifda cheksiz saqlash imkoniyati

[💎 Pro tarifga o'tish]   [Yopish]
```

### 2.4 Pro-locked Vacancy UI yaxshilash

**Hozirgi holat:** `is_pro_locked=true` bo'lsa vakansiya qoraytirilgan ko'rinadi.

**Yangi holat** (`VacancyDetail.tsx`):
```
Vakansiya ochilganda, if is_pro_locked:
┌─────────────────────────────────────┐
│ [Sarlavha, maosh, hudud — KO'RINADI]│
│                                     │
│ 🔒 Kontakt ma'lumotlari             │
│    yashirilgan                      │
│ ┌─ Tel: ••• ••• ••••           ─┐  │
│ └─ Manzil: ████████████         ─┘  │
│                                     │
│ [💎 Pro tarifga o'tish →]           │
└─────────────────────────────────────┘
```

"Pro tarifga o'tish" → `navigate("/wallet")` (hozir qilingan → confirm)

---

## SPRINT 3 — Bildirishnomalar Tizimi
**Taxminiy hajm:** ~700 satr | **Murakkablik:** Yuqori

### 3.1 DB sxema (yangi jadvallar)

```sql
-- Bildirishnoma sozlamalari
CREATE TABLE notification_settings (
    user_id     INTEGER PRIMARY KEY,
    enabled     INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
    -- Filtr users.pref_filters_json dan olinadi (global filter)
);

-- Yuborilgan bildirishnomalar tarixi
CREATE TABLE sent_notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    vacancy_uid TEXT NOT NULL,
    sent_at     INTEGER NOT NULL
);
CREATE UNIQUE INDEX idx_sent_notif_unique ON sent_notifications(user_id, vacancy_uid);
CREATE INDEX idx_sent_notif_time ON sent_notifications(user_id, sent_at);
```

### 3.2 Notification flow logikasi

**Muammo:** Osonish API real-time webhook bermaydi. Ko'p polling = blok.

**Yechim:** "Yangi vakansiya" emas — "Siz hali ko'rmagan vakansiya" konsepti.

```
Background task (har 30 daqiqada ishga tushadi):

1. notification_settings WHERE enabled=1 → user_id ro'yxati
2. Har bir user uchun:
   a. users WHERE user_id=? → is_pro=1? Agar yo'q → o'tkazib yuboradi
   b. Bugun [00:00–hozir] nechta yuborildi? COUNT(sent_notifications) → agar ≥2 → o'tkazib yuboradi
   c. Oxirgi yuborilgan vaqtdan hisoblangan "keyingi random vaqt" yetdimi?
      - Agar yo'q → o'tkazib yuboradi
   d. users.pref_filters_json dan filterlarni oladi
   e. vacancy_cache dan:
      - pref_filters ga mos keluvchi
      - sent_notifications da YO'Q bo'lgan
      - max rating/maosh bo'yicha sort
      - 1-2 ta tanlaydi
   f. Bot orqali qisqacha xabar yuboradi
   g. sent_notifications ga yozadi
   h. Keyingi random vaqtni belgilaydi (9:00–21:00 oralig'ida)
```

### 3.3 Random vaqt mexanizmi

```python
# Har foydalanuvchi uchun alohida random vaqt
# Bugungi kundizgi band: 09:00 - 21:00 oralig'ida

def next_notification_time(user_id: int) -> int:
    """Bugun uchun random vaqt (agar o'tib ketgan bo'lsa ertaga)"""
    now = datetime.now(TZ_UZB)
    
    # Deterministik random (user_id + sana asosida) — bir kun bir vaqt
    seed = user_id * 10000 + now.year * 365 + now.timetuple().tm_yday
    rng = random.Random(seed)
    
    hour = rng.randint(9, 20)
    minute = rng.randint(0, 59)
    
    target = now.replace(hour=hour, minute=minute, second=0)
    if target <= now:
        # O'tib ketgan → ertaga
        target += timedelta(days=1)
    
    return int(target.timestamp())
```

### 3.4 Bildirishnoma xabar formati

```
📌 Siz uchun ish tavsiyasi

👔 Frontend Developer
🏢 ABC Company
💰 3,000,000 – 5,000,000 so'm
📍 Toshkent shahri

🔗 Batafsil ko'rish
```

Vacancy UID dan deeplink: `https://t.me/botusername?start=vacancy_osonish_XXXXX`

### 3.5 Toggle UI

**WebApp (Profile sahifasi):**
```
YANGI qism:
┌─────────────────────────────────┐
│ 🔔 Bildirishnomalar             │
│                          [ON ●] │
│                                 │
│ Filtrlarim asosida yangi ishlar │
│ haqida kunlik xabar olasiz.     │
│                                 │
│ ⚠️ Faqat Pro tarif uchun        │  ← agar free user
└─────────────────────────────────┘
```

Agar free user toggle'ni bossa → "Pro tarifga o'ting" modal.

**Bot:**
```
/notifications komandasi → "Bildirishnomalar: [ON/OFF] — O'zgartirish" inline tugma
```

**Backend endpointlar:**
```
GET  /notifications/settings    → {enabled: bool}
POST /notifications/toggle      → {enabled: bool} → yangi holat qaytaradi
```

### 3.6 Global filter — yoqishdan oldin so'rash

Foydalanuvchi notification toggle ON qilganda:
- `pref_filters_json` bo'sh bo'lsa → avval filter o'rnatish modali ochiladi:
```
┌─────────────────────────────────────────┐
│ Birinchi, ishlaringizni sozlang         │
│                                         │
│ Hudud:    [Toshkent ▼]                  │
│ Soha:     [Barcha ▼]                    │
│ Min maosh:[Belgilash ixtiyoriy]         │
│                                         │
│ [Saqlash va yoqish]   [Keyinroq]        │
└─────────────────────────────────────────┘
```

---

## SPRINT 4 — Auto-Post Kengaytirish
**Taxminiy hajm:** ~400 satr

### 4.1 Hozirgi holat vs yangi holat

| | Hozirgi | Yangi |
|--|---------|-------|
| Kunlik sessiyalar | 1 ta | N ta random (4-8 ta post) |
| Postlar soni | 1 ta | Har random vaqtda 1 ta |
| Takrorlanish | Yo'q tracking | `posted_vacancies` jadval |
| Pauza | Yo'q | 60-90 soniya emas, alohida random vaqtlar |

### 4.2 Yangi arxitektura

"Kunduzgi random vaqtlarda, har safar 1 ta, jami 4-8 ta" tushunchasi:

```python
# Har kuni tongda: bugun nechta post qilinishi belgilanadi (4-8 oralig'ida random)
# Va qaysi vaqtlarda: N ta random vaqt (09:00-22:00)

def schedule_today_posts() -> list[int]:
    """Bugungi post vaqtlarini belgilash"""
    count = random.randint(4, 8)
    times = set()
    while len(times) < count:
        h = random.randint(9, 21)
        m = random.randint(0, 59)
        now = datetime.now(TZ_UZB).replace(hour=h, minute=m, second=0)
        times.add(int(now.timestamp()))
    return sorted(times)
```

### 4.3 DB sxema (yangi)

```sql
-- Kanalga post qilingan vakansiyalar
CREATE TABLE posted_vacancies (
    vacancy_uid TEXT NOT NULL,
    channel     TEXT NOT NULL,
    posted_at   INTEGER NOT NULL,
    PRIMARY KEY (vacancy_uid, channel)
);
CREATE INDEX idx_posted_vac_time ON posted_vacancies(posted_at);

-- webapp_admin_settings ga yangi ustun:
ALTER TABLE webapp_admin_settings 
    ADD COLUMN auto_post_per_day_min INTEGER DEFAULT 4;
ALTER TABLE webapp_admin_settings 
    ADD COLUMN auto_post_per_day_max INTEGER DEFAULT 8;
ALTER TABLE webapp_admin_settings
    ADD COLUMN auto_post_scheduled_times_json TEXT DEFAULT '[]';
    -- Misol: [1748589600, 1748610000, ...] — bugungi post vaqtlari
```

### 4.4 Yangilangan scheduler logikasi

```python
async def auto_post_loop():
    while True:
        async with aiosqlite.connect(BASE_DIR) as conn:
            # 1. Sozlamalarni olish
            settings = await get_settings(conn)
            if not settings.enabled or not settings.channel:
                await asyncio.sleep(300); continue
            
            now_ts = int(time.time())
            
            # 2. Bugungi jadval bor? Yo'q bo'lsa — yangi kun, jadval tuz
            scheduled = json.loads(settings.auto_post_scheduled_times_json or "[]")
            today_start = get_today_start_ts()  # 00:00 Toshkent
            
            today_schedule = [t for t in scheduled if t >= today_start]
            if not today_schedule:
                today_schedule = schedule_today_posts(settings)
                await save_schedule(conn, today_schedule)
                await asyncio.sleep(60); continue
            
            # 3. Yaqin vaqt yetdimi?
            next_post_ts = min((t for t in today_schedule if t > now_ts), default=None)
            if next_post_ts is None or now_ts < next_post_ts:
                await asyncio.sleep(60); continue
            
            # 4. Vakansiya tanlash (post qilinmagan, min_salary filtr)
            vacancy = await pick_unposted_vacancy(conn, settings)
            if vacancy:
                text = format_vacancy_message_html(vacancy.uid, vacancy.detail)
                await bot.send_message(settings.channel, text, disable_web_page_preview=True)
                await mark_as_posted(conn, vacancy.uid, settings.channel)
            
            # 5. Jadvaldan shu vaqtni olib tashlaymiz
            await remove_from_schedule(conn, next_post_ts)
        
        await asyncio.sleep(30)  # 30 soniyada bir tekshiradi
```

### 4.5 Takrorlanmaslik (30 kunlik oyna)

```python
async def pick_unposted_vacancy(conn, settings) -> Vacancy | None:
    thirty_days_ago = int(time.time()) - 30 * 86400
    
    # vacancy_cache dan posted_vacancies da YO'Q bo'lganlarni tanlash
    cursor = await conn.execute("""
        SELECT vc.uid, vc.data_json
        FROM vacancy_cache vc
        LEFT JOIN posted_vacancies pv ON vc.uid = pv.vacancy_uid 
            AND pv.channel = ? AND pv.posted_at > ?
        WHERE pv.vacancy_uid IS NULL
        ORDER BY RANDOM()
        LIMIT 1
    """, (settings.channel, thirty_days_ago))
    
    row = await cursor.fetchone()
    return row if row else None
```

### 4.6 Admin panel kengaytirish

`webapp/routers/admin_panel.py` + `webapp/frontend/src/pages/Admin.tsx`:

```
Auto-post sozlamalari:
┌─────────────────────────────────────┐
│ ☑️ Auto-post yoqilgan              │
│ Kanal: @bandlikuz                   │
│ Min maosh: 2,000,000 so'm           │
│ Kunlik post soni: 4 [min] — 8 [max] │
│                                     │
│ Bugungi jadval:                     │
│ ✅ 09:24 — osonish_12345 yuborildi  │
│ ⏳ 12:47 — kutilmoqda              │
│ ⏳ 17:03 — kutilmoqda              │
└─────────────────────────────────────┘
```

---

## SPRINT 5 — Haftalik Statistika (Har Juma)
**Taxminiy hajm:** ~500 satr

### 5.1 Ma'lumot manbalari

| Ko'rsatkich | Manba | Qanday olinadi |
|-------------|-------|----------------|
| Yangi foydalanuvchilar (+haftalik) | users jadvali | SQL COUNT |
| Jami foydalanuvchilar | users jadvali | SQL COUNT |
| Pro foydalanuvchilar | users jadvali | SQL WHERE user_pro=1 |
| Saqlangan ishlar (haftalik) | saves jadvali | SQL COUNT (7 kun) |
| Resume yaratildi | resume_events | SQL (event=ready) |
| Aktiv vakansiyalar soni | Osonish API | 1 ta GET so'rov |
| O'rtacha maosh | vacancy_cache | AVG(salary) |
| Top 5 soha | vacancy_cache | GROUP BY specialty |
| Top 5 hudud | vacancy_cache | GROUP BY region |
| Haftalik maosh trend | — | Oldingi 4 hafta avg (cache) |

### 5.2 Grafik generatsiya (matplotlib + PIL)

```python
# src/functions/stats_chart.py

import matplotlib
matplotlib.use('Agg')  # Headless (server-side)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO

def generate_weekly_stats_chart(stats: WeeklyStats) -> bytes:
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.patch.set_facecolor('#F8FAFC')
    fig.suptitle(f"Haftalik statistika — {stats.week_label}", 
                 fontsize=14, fontweight='bold', color='#1E293B')
    
    # [0,0] Top 5 soha — gorizontal bar chart
    ax1 = axes[0, 0]
    ax1.barh(stats.top_specs[:5], stats.top_specs_counts[:5], color='#0EA5E9')
    ax1.set_title("Top sohalar", fontsize=10)
    
    # [0,1] Top 5 hudud — bar chart
    ax2 = axes[0, 1]
    ax2.bar(stats.top_regions[:5], stats.top_region_counts[:5], color='#10B981')
    ax2.tick_params(axis='x', rotation=30)
    ax2.set_title("Top hududlar", fontsize=10)
    
    # [1,0] Foydalanuvchi o'sish — line chart (4 hafta)
    ax3 = axes[1, 0]
    ax3.plot(stats.weeks_labels, stats.users_per_week, 
             marker='o', color='#8B5CF6', linewidth=2)
    ax3.set_title("Foydalanuvchi o'sishi", fontsize=10)
    ax3.fill_between(stats.weeks_labels, stats.users_per_week, alpha=0.15, color='#8B5CF6')
    
    # [1,1] O'rtacha maosh trend (4 hafta) — line chart
    ax4 = axes[1, 1]
    ax4.plot(stats.weeks_labels, stats.avg_salary_per_week,
             marker='s', color='#F59E0B', linewidth=2)
    ax4.set_title("O'rtacha maosh (so'm)", fontsize=10)
    ax4.yaxis.set_major_formatter(lambda x, _: f"{x/1e6:.1f}M")
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='PNG', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()
```

### 5.3 Statistika xabar matni (grafik bilan birga)

```
📊 Haftalik statistika | 26-may – 1-iyun 2026

👥 Foydalanuvchilar
   +127 yangi (jami: 4,832 ta)
   💎 Pro: 89 ta

💼 Vakansiyalar
   Aktiv e'lonlar: ~1,240 ta
   O'rtacha maosh: 3,200,000 so'm

🏆 Top 3 soha:
   1. IT/Texnologiya — 320 ta
   2. Savdo/Marketing — 280 ta
   3. Qurilish — 195 ta

📍 Top 3 hudud:
   1. Toshkent — 890 ta
   2. Samarqand — 145 ta
   3. Andijon — 120 ta

📄 Resume yaratildi: 89 ta
❤️ Saqlangan: 312 ta

📈 @bandlikuz
```

### 5.4 Scheduler

```python
# src/functions/weekly_stats_scheduler.py

async def weekly_stats_loop():
    while True:
        try:
            now = datetime.now(TZ_UZB)
            # Har juma, soat 10:00-10:05 oralig'ida yuboriladi
            if now.weekday() == 4 and now.hour == 10 and now.minute < 5:
                stats = await collect_weekly_stats()
                chart_bytes = generate_weekly_stats_chart(stats)
                text = format_stats_message(stats)
                
                # Grafik + matn birga
                await bot.send_photo(
                    chat_id=channel,
                    photo=BufferedInputFile(chart_bytes, "stats.png"),
                    caption=text
                )
                
                # Bir soat kutadi (bir juma bir marta)
                await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Weekly stats error: {e}")
        
        await asyncio.sleep(240)  # 4 daqiqada bir tekshiradi
```

### 5.5 Vacancy cache'dan statistika olish

```python
async def collect_weekly_stats() -> WeeklyStats:
    week_ago = int(time.time()) - 7 * 86400
    
    async with aiosqlite.connect(DB_PATH) as conn:
        # Foydalanuvchi statistikasi
        new_users = await count(conn, "users WHERE date >= ?", week_ago)
        total_users = await count(conn, "users")
        pro_users = await count(conn, "users WHERE user_pro = 1")
        
        # Resume statistikasi
        resumes = await count(conn, 
            "resume_events WHERE event_name='ready' AND created_at >= ?", week_ago)
        
        # Saves statistikasi
        saves = await count(conn, "saves WHERE saved_at >= ?", week_ago)
        
        # Vacancy cache dan soha/hudud statistikasi
        spec_stats = await get_spec_distribution(conn)
        region_stats = await get_region_distribution(conn)
        avg_salary = await get_avg_salary(conn)
        
        # 4 haftali trend (SQLite window function yoki manual)
        trend = await get_4week_trend(conn)
    
    # Osonish API dan aktiv vakansiyalar soni (1 marta)
    total_vacancies = await fetch_total_vacancy_count()
    
    return WeeklyStats(
        week_label=format_week_label(),
        new_users=new_users,
        ...
    )
```

---

## Umumiy texnik o'zgarishlar

### Yangi fayllar (jami)

```
src/
  data/
    law_articles.py        ← Qonunchilik maqolalari (12 ta)
    hr_tips.py             ← HR maslahatlar (2-3 ta)
  functions/
    stats_chart.py         ← matplotlib grafik generatsiya
    weekly_stats_scheduler.py ← Juma scheduleri
  handlers/
    content.py             ← Bot Qonunchilik + HR handlerlar

webapp/
  routers/
    content.py             ← GET /content/laws, /content/laws/{id}
    notifications.py       ← GET/POST /notifications/settings, /toggle
  frontend/src/
    pages/
      Laws.tsx             ← Qonunchilik sahifasi
    components/
      GlobalFilterModal.tsx ← Bildirishnomalardan oldin so'raladigan filtr modal
```

### O'zgartirilajak mavjud fayllar

```
src/handlers/start.py           ← Reply keyboard kengaytirish
src/functions/auto_post_scheduler.py ← Ko'p sessiyli scheduler
main.py                         ← Yangi schedulerlarni ro'yxatga olish

webapp/routers/resume.py        ← Template lock (FREE_TEMPLATES set)
webapp/routers/saves.py         ← 5 ta limit
webapp/routers/admin_panel.py   ← Yangi sozlamalar
webapp/core/database.py         ← Yangi jadvallar migration

webapp/frontend/src/
  App.tsx                       ← /hub/laws route
  pages/Hub.tsx                 ← Qonunchilik kartochkasi
  pages/Profile.tsx             ← Notification toggle + Global filter
  pages/ResumeStudio.tsx        ← Template lock UI
  hooks/useSaves.ts             ← 403 SAVE_LIMIT_REACHED handling
  components/Jobs/VacancyDetail.tsx ← Pro-lock yaxshilash
```

### Yangi DB jadvallar (migration)

```sql
-- notification_settings
-- sent_notifications  
-- posted_vacancies

-- Mavjud jadvallar kengaytmasi:
ALTER TABLE users ADD COLUMN pref_filters_json TEXT;
ALTER TABLE webapp_admin_settings ADD COLUMN auto_post_per_day_min INTEGER DEFAULT 4;
ALTER TABLE webapp_admin_settings ADD COLUMN auto_post_per_day_max INTEGER DEFAULT 8;
ALTER TABLE webapp_admin_settings ADD COLUMN auto_post_scheduled_times_json TEXT DEFAULT '[]';
```

### Yangi dependencies

```
matplotlib  — haftalik statistika grafiklari
# Pillow allaqachon o'rnatilgan ✅
# aiosqlite, aiogram, fastapi — allaqachon bor ✅
```

---

## Sprint ketma-ketligi (tavsiya)

```
Sprint 1 (3-4 kun) — Kontent Hub
  → law_articles.py, hr_tips.py
  → webapp/routers/content.py
  → webapp/frontend/src/pages/Laws.tsx
  → Hub.tsx kengaytirish
  → Bot: content.py handler, reply keyboard
  
Sprint 2 (3-4 kun) — Premium Enforcement
  → users.pref_filters_json migration
  → Resume template lock (backend + frontend)
  → Saves 5 ta limit (backend + frontend)
  → Pro-lock vacancy detail yaxshilash
  
Sprint 3 (5-6 kun) — Bildirishnomalar
  → DB: notification_settings, sent_notifications
  → notifications.py router
  → Notification scheduler background task
  → Profile.tsx: toggle + global filter modal
  → Bot: /notifications handler
  
Sprint 4 (3-4 kun) — Auto-Post Ko'p Sessiyli
  → DB: posted_vacancies + admin settings kengaytma
  → auto_post_scheduler.py to'liq qayta yozish
  → Admin panel yangi sozlamalar
  
Sprint 5 (4-5 kun) — Haftalik Statistika
  → stats_chart.py (matplotlib)
  → weekly_stats_scheduler.py
  → main.py ga qo'shish
  → matplotlib o'rnatish + server deploy
```

---

## Muhim eslatmalar

1. **SQLite concurrent write** — bot va FastAPI bir DBga yozadi. `PRAGMA journal_mode=WAL` allaqachon o'rnatilgan ✅. Notification scheduler ham aiosqlite ishlatishi kerak.

2. **Osonish API rate limit** — bildirishnomalar uchun API'ga yangi so'rov YO'Q, faqat `vacancy_cache` ishlatiladi. Haftalik statistika uchun 1 marta GET so'rov — xavfsiz.

3. **matplotlib server'da** — `matplotlib.use('Agg')` server-side (GUI yo'q) uchun backend o'rnatilishi shart. `pip install matplotlib` va server'da ham o'rnatish kerak.

4. **Bot reply keyboard** — hozirgi botda faqat inline keyboard bor. Reply keyboard qo'shilganda barcha foydalanuvchilarga ko'rsatilmaydi — keyingi xabar yuborilganda avtomatik ko'rinadi.

5. **Template lock bypass** — frontend'da blokash yetarli emas, backend'da ham tekshiruv bo'lishi shart (kimdir API'ga to'g'ridan to'g'ri murojaat qilmasligi uchun).

6. **posted_vacancies tozalash** — 30 kundan eski yozuvlar schedulerni endi yuk bo'lmasligi uchun muntazam o'chiriladi (30 kunda bir marta DELETE).

---

*Fayl: `/home/adhambek/projects/pythons/vakant3/ROADMAP.md`*
*Keyingi qadam: Sprint 1 ni boshlash — `src/data/law_articles.py`dan*
