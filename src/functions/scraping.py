import asyncio
import aiohttp
import re
from typing import Optional, Dict, List, Tuple
from bs4 import BeautifulSoup
import time


class ProxyManager:
    """O'zbekiston proxy'larini boshqarish"""

    def __init__(self):
        self.proxies: List[str] = []
        self.working_proxies: List[Tuple[str, float]] = []  # (proxy, response_time)
        self.last_fetch_time = 0
        self.cache_duration = 300  # 5 daqiqa

    async def fetch_uzbek_proxies(self) -> List[str]:
        """Spys.one dan O'zbekiston proxy'larini olish"""
        current_time = time.time()

        # Cache tekshirish
        if self.proxies and (current_time - self.last_fetch_time) < self.cache_duration:
            return self.proxies

        url = "https://spys.one/free-proxy-list/UZ/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
        }

        proxies = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=20, ssl=False) as resp:
                    if resp.status != 200:
                        print(f"Spys.one response status: {resp.status}")
                        return []

                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # spy1x class'li qatorlarni topish
                    rows = soup.find_all('tr', class_='spy1x')

                    for row in rows[:30]:  # Birinchi 30 ta
                        try:
                            td = row.find('td')
                            if not td:
                                continue

                            # IP ni topish
                            font = td.find('font', class_='spy14')
                            if not font:
                                continue

                            text = font.get_text(strip=True)

                            # IP regex
                            ip_match = re.match(r'(\d+\.\d+\.\d+\.\d+)', text)
                            if not ip_match:
                                continue

                            ip = ip_match.group(1)

                            # Port ni script'dan decode qilish
                            script = font.find('script')
                            if script and script.string:
                                port = self._decode_port(script.string, html)
                                if port:
                                    proxy = f"http://{ip}:{port}"
                                    proxies.append(proxy)
                                    continue

                            # Agar script decode qilmasa, oddiy :port ni qidirish
                            port_match = re.search(r':(\d+)', text)
                            if port_match:
                                port = port_match.group(1)
                                proxies.append(f"http://{ip}:{port}")

                        except Exception as e:
                            continue

                    self.proxies = proxies
                    self.last_fetch_time = current_time
                    print(f"✓ {len(proxies)} ta proxy topildi")
                    return proxies

        except Exception as e:
            print(f"Proxy fetch error: {str(e)}")
            return []

    def _decode_port(self, script_text: str, full_html: str) -> Optional[int]:
        """Spys.one obfuscated port'ini decode qilish"""
        try:
            # Script ichidan variable'larni topish
            operations = re.findall(r'(\w+)\^(\w+)', script_text)
            if not operations:
                return None

            # HTML'dan variable qiymatlarini olish
            var_pattern = r'<script[^>]*>([^<]*var [^<]+)</script>'
            scripts = re.findall(var_pattern, full_html, re.DOTALL)

            var_map = {}
            for script in scripts:
                # var SevenSevenEightFive=7785; formatidagi qiymatlarni topish
                var_assigns = re.findall(r'var (\w+)=(\d+);', script)
                var_map.update(var_assigns)

            # Port raqamini qurish
            port_digits = []
            for var1, var2 in operations:
                val1 = int(var_map.get(var1, 0))
                val2 = int(var_map.get(var2, 0))
                result = val1 ^ val2
                port_digits.append(str(result))

            port_str = ''.join(port_digits)
            if port_str and port_str.isdigit():
                port = int(port_str)
                if 1 <= port <= 65535:
                    return port

            return None

        except Exception:
            return None

    async def test_proxy(self, proxy: str, timeout: int = 8) -> Optional[float]:
        """Proxy'ni test qilish va response time'ni qaytarish"""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        'https://api.ipify.org?format=json',
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        ssl=False
                ) as resp:
                    if resp.status == 200:
                        elapsed = time.time() - start_time
                        return elapsed
                    return None
        except:
            return None

    async def get_working_proxies(self, max_proxies: int = 10) -> List[str]:
        """Ishlaydigan proxy'larni topish"""
        if not self.proxies:
            await self.fetch_uzbek_proxies()

        if not self.proxies:
            return []

        # Parallel test qilish
        test_proxies = self.proxies[:max_proxies * 2]  # Ikki baravar ko'p test qilish
        tasks = [self.test_proxy(proxy) for proxy in test_proxies]
        results = await asyncio.gather(*tasks)

        # Ishlaydigan va tezlarini saralash
        working = []
        for proxy, response_time in zip(test_proxies, results):
            if response_time is not None:
                working.append((proxy, response_time))

        # Response time bo'yicha saralash
        working.sort(key=lambda x: x[1])

        self.working_proxies = working[:max_proxies]

        if working:
            print(f"✓ {len(working)} ta ishlaydigan proxy topildi")
            for proxy, rt in working[:3]:
                print(f"  • {proxy} ({rt:.2f}s)")

        return [proxy for proxy, _ in self.working_proxies]


class APIFetcher:
    """API'dan ma'lumot olish"""

    def __init__(self):
        self.proxy_manager = ProxyManager()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]

    async def fetch_with_proxy(self, url: str, proxy: str, timeout: int = 30) -> Optional[Dict]:
        """Bitta proxy bilan so'rov yuborish"""
        import random

        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://ish.mehnat.uz/',
            'Origin': 'https://ish.mehnat.uz',
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        url,
                        proxy=proxy,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        ssl=False
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
                    elif resp.status == 403:
                        print(f"  ✗ {proxy} - 403 Forbidden")
                    elif resp.status == 503:
                        print(f"  ✗ {proxy} - 503 Service Unavailable")
                    return None
        except asyncio.TimeoutError:
            print(f"  ✗ {proxy} - Timeout")
        except aiohttp.ClientError as e:
            print(f"  ✗ {proxy} - {type(e).__name__}")
        except Exception:
            pass

        return None

    async def fetch(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """Proxy'lar orqali ma'lumot olish (retry bilan)"""

        # 1. To'g'ridan-to'g'ri urinish (test uchun)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        print("✓ To'g'ridan-to'g'ri ulanish muvaffaqiyatli")
                        return await resp.json()
        except:
            print("✗ To'g'ridan-to'g'ri ulanish bloklangan")

        # 2. Proxy'lar orqali
        print("Proxy'larni topish...")
        working_proxies = await self.proxy_manager.get_working_proxies(max_proxies=10)

        if not working_proxies:
            print("✗ Ishlaydigan proxy topilmadi")
            return None

        print(f"\nAPI'ga ulanish: {url[:80]}...")

        # Har bir proxy bilan urinish
        for attempt in range(max_retries):
            for proxy in working_proxies:
                print(f"  Urinish: {proxy}")
                data = await self.fetch_with_proxy(url, proxy, timeout=45)

                if data:
                    print(f"✓ Muvaffaqiyatli! Proxy: {proxy}")
                    return data

                await asyncio.sleep(0.5)

            if attempt < max_retries - 1:
                print(f"\nRetry {attempt + 2}/{max_retries}...")
                await asyncio.sleep(2)

        print("✗ Barcha urinishlar muvaffaqiyatsiz")
        return None


# Global fetcher instance
_fetcher = APIFetcher()


async def get_site_content(URL: str) -> Optional[Dict]:
    """
    Asosiy funksiya - proxy orqali API'dan ma'lumot olish

    Bu funksiya loyihaning qolgan qismida ishlatiladi va
    aiohttp.ClientSession bilan bir xil formatda javob qaytaradi.

    Args:
        URL: API endpoint

    Returns:
        JSON ma'lumot yoki None
    """
    return await _fetcher.fetch(URL, max_retries=3)


# Test uchun
async def test_scraping():
    """Scraping test qilish"""
    print("=" * 70)
    print("SCRAPING TEST")
    print("=" * 70)

    # Test URL
    test_url = (
        'https://ishapi.mehnat.uz/api/v1/vacancies?'
        'per_page=5&vacancy_soato_code=1733&'
        'sort_key=created_at&nskz=213,312&page=1'
    )

    data = await get_site_content(test_url)

    if data:
        print("\n" + "=" * 70)
        print("SUCCESS!")
        print("=" * 70)

        if 'data' in data and 'data' in data['data']:
            vacancies = data['data']['data']
            print(f"\nTopildi: {len(vacancies)} ta vakansiya")

            for i, v in enumerate(vacancies[:3], 1):
                print(f"\n{i}. {v.get('position_name', 'N/A')}")
                print(f"   Kompaniya: {v.get('company_name', 'N/A')}")
                print(f"   Maosh: {v.get('position_salary', 'N/A')}")
        else:
            print(f"Ma'lumot formati: {list(data.keys())}")
    else:
        print("\n" + "=" * 70)
        print("FAILED - Ma'lumot olinmadi")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_scraping())