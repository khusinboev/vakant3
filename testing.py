import asyncio
import aiohttp
import json
from typing import List, Dict, Optional
from datetime import datetime
import random
from urllib.parse import urlencode


class VacancyScraper:
    """
    Mehnat.uz API'dan vakansiya ma'lumotlarini olish uchun professional scraper.
    Xavfsizlik choralarini aylanib o'tish va ishonchli ishlash uchun optimallashtirilgan.
    """

    def __init__(self):
        self.base_url = "https://ishapi.mehnat.uz/api/v1/vacancies"

        # Real brauzer User-Agent'lari - botlikni yashirish uchun
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        ]

        # Real brauzer header'lari - to'liq legitimlik uchun
        self.base_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

        # Statistika
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_vacancies': 0
        }

    def _get_random_headers(self) -> Dict[str, str]:
        """Har safar random User-Agent bilan header qaytaradi"""
        headers = self.base_headers.copy()
        headers['User-Agent'] = random.choice(self.user_agents)
        headers['Referer'] = 'https://ish.mehnat.uz/'
        headers['Origin'] = 'https://ish.mehnat.uz'
        return headers

    async def _make_request(
            self,
            session: aiohttp.ClientSession,
            params: Dict,
            retry: int = 3
    ) -> Optional[Dict]:
        """
        So'rov yuborish va retry mexanizmi bilan javob olish
        """
        for attempt in range(retry):
            try:
                self.stats['total_requests'] += 1

                # Random header har safar
                headers = self._get_random_headers()

                async with session.get(
                        self.base_url,
                        params=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                        ssl=False  # SSL verification'ni o'chirish (agar kerak bo'lsa)
                ) as response:

                    # Rate limiting'ni aylanib o'tish uchun kutish
                    if response.status == 429:
                        wait_time = (2 ** attempt) + random.uniform(1, 3)
                        print(f"⚠️  Rate limit! {wait_time:.1f}s kutilmoqda...")
                        await asyncio.sleep(wait_time)
                        continue

                    if response.status == 200:
                        self.stats['successful_requests'] += 1
                        data = await response.json()
                        return data
                    else:
                        print(f"❌ Xato: Status {response.status}")

            except asyncio.TimeoutError:
                print(f"⏱️  Timeout! Urinish {attempt + 1}/{retry}")
                await asyncio.sleep(random.uniform(2, 5))

            except aiohttp.ClientError as e:
                print(f"❌ Network xato: {e}")
                await asyncio.sleep(random.uniform(2, 5))

            except Exception as e:
                print(f"❌ Kutilmagan xato: {e}")

        self.stats['failed_requests'] += 1
        return None

    async def get_vacancies(
            self,
            region_code: str = "1733",
            professions: List[str] = None,
            per_page: int = 20,
            max_pages: Optional[int] = None,
            delay_range: tuple = (1, 3)
    ) -> List[Dict]:
        """
        Vakansiyalarni olish - asosiy metod

        Args:
            region_code: Hudud kodi (1733 - Xorazm)
            professions: Kasb kodlari ro'yxati (213,312 - IT kasblar)
            per_page: Har bir sahifada vakansiyalar soni
            max_pages: Maksimal sahifalar soni (None = hammasi)
            delay_range: So'rovlar orasidagi kutish vaqti (soniyada)
        """

        if professions is None:
            professions = ["213", "312"]  # IT kasblar default

        all_vacancies = []
        page = 1

        # TCP connection pooling uchun connector
        connector = aiohttp.TCPConnector(
            limit=10,  # Maksimal parallel ulanishlar
            ttl_dns_cache=300,  # DNS cache
            limit_per_host=5
        )

        # Cookie jar - session'ni saqlash uchun
        jar = aiohttp.CookieJar()

        async with aiohttp.ClientSession(connector=connector, cookie_jar=jar) as session:

            while True:
                # Parametrlarni to'g'ri formatlash
                params = {
                    'per_page': per_page,
                    'kodp_keys': '[]',  # Bo'sh array string sifatida
                    'vacancy_soato_code': region_code,
                    'pagination_type': 'simplePaginate',
                    'sort_key': 'created_at',
                    'nskz': ','.join(professions),
                    'is_reserved': '0',
                    'for_students': '0',
                    'isVisible': 'true',  # true qilib o'zgartirdik
                    'page': page
                }

                print(f"📄 Sahifa {page} yuklanmoqda...")

                # So'rov yuborish
                data = await self._make_request(session, params)

                if not data or not data.get('success'):
                    print(f"❌ Sahifa {page} yuklanmadi!")
                    break

                vacancies = data.get('data', {}).get('data', [])

                if not vacancies:
                    print(f"✅ Barcha sahifalar yuklandi! (Jami: {page - 1} sahifa)")
                    break

                all_vacancies.extend(vacancies)
                self.stats['total_vacancies'] += len(vacancies)

                print(f"✅ {len(vacancies)} ta vakansiya olindi")

                # Max pages check
                if max_pages and page >= max_pages:
                    print(f"🛑 Maksimal sahifa limitiga yetildi: {max_pages}")
                    break

                # Keyingi sahifa bormi tekshirish
                next_page = data.get('data', {}).get('next_page_url')
                if not next_page:
                    print("✅ Oxirgi sahifaga yetildi!")
                    break

                page += 1

                # Rate limiting'dan qochish uchun random delay
                delay = random.uniform(*delay_range)
                print(f"⏳ {delay:.1f}s kutilmoqda...")
                await asyncio.sleep(delay)

        return all_vacancies

    def parse_vacancy(self, vacancy: Dict) -> Dict:
        """Vakansiya ma'lumotlarini tozalash va formatlash"""

        # Company profile data'ni parse qilish
        company = vacancy.get('company', {})
        profile_data = {}

        try:
            profile_str = company.get('profile_data', '{}')
            profile_data = json.loads(profile_str)
        except:
            pass

        return {
            'id': vacancy.get('id'),
            'kompaniya': vacancy.get('company_name'),
            'stir': vacancy.get('company_tin'),
            'lavozim': vacancy.get('position_name'),
            'lavozim_ru': vacancy.get('position_name_ru'),
            'maosh': float(vacancy.get('position_salary', 0)),
            'stavka': float(vacancy.get('position_rate', 1)),
            'bolim': vacancy.get('structure_name'),
            'boshlanish_sana': vacancy.get('date_start'),
            'hudud_kod': vacancy.get('company_soato_code'),
            'direktor': profile_data.get('director'),
            'telefon': profile_data.get('phone_vacancies'),
            'manzil': profile_data.get('address'),
            'haqiqiy_manzil': profile_data.get('actual_address'),
        }

    def save_to_json(self, vacancies: List[Dict], filename: str = "vacancies.json"):
        """Ma'lumotlarni JSON faylga saqlash"""
        parsed_vacancies = [self.parse_vacancy(v) for v in vacancies]

        output = {
            'sana': datetime.now().isoformat(),
            'jami_vakansiya': len(parsed_vacancies),
            'statistika': self.stats,
            'vakansiyalar': parsed_vacancies
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n💾 {filename} faylga saqlandi!")

    def print_statistics(self):
        """Statistikani chiqarish"""
        print("\n" + "=" * 60)
        print("📊 STATISTIKA")
        print("=" * 60)
        print(f"Jami so'rovlar: {self.stats['total_requests']}")
        print(f"Muvaffaqiyatli: {self.stats['successful_requests']}")
        print(f"Muvaffaqiyatsiz: {self.stats['failed_requests']}")
        print(f"Jami vakansiyalar: {self.stats['total_vacancies']}")
        print("=" * 60 + "\n")


# ============================================================================
# ISHLATISH MISOLLARI
# ============================================================================

async def main():
    """Asosiy funksiya - barcha misollar"""

    scraper = VacancyScraper()

    print("🚀 Vakansiya Scraper ishga tushdi!\n")

    # MISOL 1: Xorazm viloyatidan IT vakansiyalarini olish (5 sahifa)
    print("📌 MISOL 1: Xorazm - IT vakansiyalar (5 sahifa)")
    vacancies = await scraper.get_vacancies(
        region_code="1733",
        professions=["213", "312"],  # IT kasblar
        per_page=20,
        max_pages=5,
        delay_range=(1, 2)  # 1-2 soniya orasida kutish
    )

    # Natijalarni ko'rsatish
    print(f"\n✅ Jami {len(vacancies)} ta vakansiya olindi!\n")

    # Birinchi 3 ta vakansiyani ko'rsatish
    print("📋 Birinchi 3 ta vakansiya:")
    for i, v in enumerate(vacancies[:3], 1):
        parsed = scraper.parse_vacancy(v)
        print(f"\n{i}. {parsed['lavozim']}")
        print(f"   Kompaniya: {parsed['kompaniya']}")
        print(f"   Maosh: {parsed['maosh']:,.0f} UZS")
        print(f"   Telefon: {parsed['telefon']}")

    # Faylga saqlash
    scraper.save_to_json(vacancies, "xorazm_it_vacancies.json")

    # Statistika
    scraper.print_statistics()


async def example_all_regions():
    """MISOL 2: Barcha hududlardan ma'lumot olish"""

    scraper = VacancyScraper()

    regions = {
        "1701": "Toshkent sh.",
        "1709": "Toshkent vil.",
        "1733": "Xorazm",
        "1726": "Samarqand",
        "1714": "Farg'ona"
    }

    all_data = {}

    for code, name in regions.items():
        print(f"\n🏙️  {name} ({code}) yuklanmoqda...")
        vacancies = await scraper.get_vacancies(
            region_code=code,
            professions=["213", "312"],
            per_page=50,
            max_pages=2,
            delay_range=(2, 4)
        )
        all_data[name] = vacancies
        print(f"✅ {name}: {len(vacancies)} ta vakansiya")

    # Hammasi bitta faylga
    with open("all_regions_vacancies.json", 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n💾 all_regions_vacancies.json faylga saqlandi!")


async def example_specific_search():
    """MISOL 3: Maxsus qidiruv - faqat dasturchilar"""

    scraper = VacancyScraper()

    print("🔍 Faqat dasturchilar qidirilmoqda...\n")

    vacancies = await scraper.get_vacancies(
        region_code="1733",
        professions=["213"],  # Faqat dasturchilar
        per_page=100,
        max_pages=10,
        delay_range=(1.5, 3)
    )

    # Filtrlash - "dasturchi" so'zi bor lavozimlar
    programmers = [
        v for v in vacancies
        if 'дастур' in v.get('position_name', '').lower() or
           'программ' in v.get('position_name_ru', '').lower()
    ]

    print(f"\n✅ {len(programmers)} ta dasturchi vakansiyasi topildi!")

    # Top 3 eng yuqori maoshli
    sorted_by_salary = sorted(
        programmers,
        key=lambda x: float(x.get('position_salary', 0)),
        reverse=True
    )

    print("\n💰 Top 3 eng yuqori maoshli:")
    for i, v in enumerate(sorted_by_salary[:3], 1):
        parsed = scraper.parse_vacancy(v)
        print(f"\n{i}. {parsed['lavozim']}")
        print(f"   Maosh: {parsed['maosh']:,.0f} UZS")
        print(f"   Kompaniya: {parsed['kompaniya']}")

    scraper.save_to_json(programmers, "programmers_only.json")


# ============================================================================
# ISHGA TUSHIRISH
# ============================================================================

if __name__ == "__main__":
    # Asosiy misol
    asyncio.run(main())

    # Boshqa misollar uchun:
    # asyncio.run(example_all_regions())
    # asyncio.run(example_specific_search())