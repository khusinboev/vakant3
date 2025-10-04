import requests
import json
import time
import random
from datetime import datetime
import pandas as pd
from typing import Dict, List, Optional


class IshMehnatScraper:
    def __init__(self):
        self.base_url = "https://ishapi.mehnat.uz/api/v1/vacancies"
        self.session = requests.Session()
        self.setup_headers()

    def setup_headers(self):
        """Real brauzerga o'xshash headerslarni sozlash"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'uz,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://ish.mehnat.uz/vacancies',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
        self.session.headers.update(self.headers)

    def random_delay(self):
        """Rate limitingni aylanib o'tish uchun tasodifiy kechikish"""
        time.sleep(random.uniform(1, 3))

    def make_request(self, page: int, per_page: int = 50) -> Optional[Dict]:
        """API ga so'rov yuborish"""
        params = {
            'per_page': per_page,
            'kodp_keys': '[]',
            'vacancy_soato_code': '1733',
            'pagination_type': 'simplePaginate',
            'sort_key': 'created_at',
            'nskz': '213,312',
            'is_reserved': '0',
            'for_students': '0',
            'isVisible': 'true',
            'page': page
        }

        try:
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=30
            )

            # Xavfsizlik tekshiruvlarini aylanib o'tish
            if response.status_code == 429:  # Rate limiting
                print("Rate limiting aniqlandi, 60 soniya kutamiz...")
                time.sleep(60)
                return self.make_request(page, per_page)

            elif response.status_code == 403:  # Access denied
                print("Access denied, headers yangilanmoqda...")
                self.setup_headers()
                time.sleep(10)
                return self.make_request(page, per_page)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"So'rovda xatolik (sahifa {page}): {e}")
            return None

    def parse_company_data(self, profile_data: str) -> Dict:
        """Company ma'lumotlarini parse qilish"""
        try:
            if profile_data:
                return json.loads(profile_data)
        except:
            pass
        return {}

    def extract_vacancy_info(self, vacancy: Dict) -> Dict:
        """Vakansiya ma'lumotlarini chiqarib olish"""
        company_data = self.parse_company_data(vacancy.get('company', {}).get('profile_data', ''))

        return {
            'id': vacancy.get('id'),
            'company_name': vacancy.get('company_name'),
            'company_tin': vacancy.get('company_tin'),
            'position_name': vacancy.get('position_name'),
            'position_name_ru': vacancy.get('position_name_ru'),
            'salary': vacancy.get('position_salary'),
            'rate': vacancy.get('position_rate'),
            'structure_name': vacancy.get('structure_name'),
            'start_date': vacancy.get('date_start'),
            'region_code': vacancy.get('company_soato_code4'),
            'district_code': vacancy.get('company_soato_code7'),
            'director': company_data.get('director'),
            'phone': company_data.get('phone_vacancies'),
            'address': company_data.get('address'),
            'actual_address': company_data.get('actual_address')
        }

    def get_all_vacancies(self, max_pages: int = 100) -> List[Dict]:
        """Barcha vakansiyalarni olish"""
        all_vacancies = []

        for page in range(1, max_pages + 1):
            print(f"Sahifa {page} yuklanmoqda...")

            data = self.make_request(page)
            if not data or not data.get('success'):
                print(f"Sahifa {page} da ma'lumot yo'q yoki xatolik")
                break

            vacancies = data.get('data', {}).get('data', [])
            if not vacancies:
                print("Barcha sahifalar yuklandi")
                break

            for vacancy in vacancies:
                parsed_vacancy = self.extract_vacancy_info(vacancy)
                all_vacancies.append(parsed_vacancy)

            print(f"Sahifa {page} yuklandi. Jami: {len(all_vacancies)} ta vakansiya")

            # Keyingi sahifa mavjudligini tekshirish
            next_page = data.get('data', {}).get('next_page_url')
            if not next_page:
                print("Keyingi sahifa yo'q")
                break

            self.random_delay()

        return all_vacancies

    def save_to_excel(self, vacancies: List[Dict], filename: str = None):
        """Ma'lumotlarni Excel faylga saqlash"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'ish_vacancies_{timestamp}.xlsx'

        df = pd.DataFrame(vacancies)
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"Ma'lumotlar {filename} fayliga saqlandi")

    def save_to_json(self, vacancies: List[Dict], filename: str = None):
        """Ma'lumotlarni JSON faylga saqlash"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'ish_vacancies_{timestamp}.json'

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(vacancies, f, ensure_ascii=False, indent=2)
        print(f"Ma'lumotlar {filename} fayliga saqlandi")


def main():
    """Asosiy funksiya"""
    scraper = IshMehnatScraper()

    print("Vakansiyalar yuklanmoqda...")
    vacancies = scraper.get_all_vacancies(max_pages=50)

    if vacancies:
        print(f"Jami {len(vacancies)} ta vakansiya topildi")

        # Excel faylga saqlash
        scraper.save_to_excel(vacancies)

        # JSON faylga saqlash
        scraper.save_to_json(vacancies)

        # Bir nechta vakansiyalarni ko'rsatish
        print("\nBirinchi 5 ta vakansiya:")
        for i, vac in enumerate(vacancies[:5]):
            print(f"{i + 1}. {vac['position_name']} - {vac['company_name']} - {vac['salary']} so'm")
    else:
        print("Hech qanday vakansiya topilmadi")


if __name__ == "__main__":
    main()