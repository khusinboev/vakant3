import asyncio
import aiohttp
import re
import time
from typing import List, Tuple, Optional, Any
from bs4 import BeautifulSoup, NavigableString


class ProxyManager:
    """O'zbekiston proxy'larini boshqarish va spys.one obfuskatsiyasini yechish."""

    _instance = None  # Singleton pattern uchun

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.proxies: List[str] = []
        self.working_proxies: List[Tuple[str, float]] = []
        self.last_fetch_time = 0
        self.cache_duration = 300  # 5 daqiqa
        self._initialized = True

    async def fetch_uzbek_proxies(self, max_rows: int = 50) -> List[str]:
        """Spys.one dan O'zbekiston proxy'larini o'qish va portlarni decode qilish."""
        current_time = time.time()
        if self.proxies and (current_time - self.last_fetch_time) < self.cache_duration:
            print(f"✓ Cache'dan {len(self.proxies)} ta proxy ishlatilmoqda")
            return self.proxies

        url = "https://spys.one/free-proxy-list/UZ/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        proxies: List[str] = []
        try:
            print("🔄 Yangi proxy'lar yuklanmoqda...")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=20) as resp:
                    if resp.status != 200:
                        print(f"❌ Spys.one response status: {resp.status}")
                        return self.proxies if self.proxies else []

                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Sahifadagi barcha var assignlarni yig'ib olamiz
                    var_assigns = re.findall(r'var\s+([A-Za-z0-9_]+)\s*=\s*(\d+);', html)
                    var_map = {name: int(val) for name, val in var_assigns}

                    rows = soup.find_all('tr', class_='spy1x')
                    for row in rows[:max_rows]:
                        try:
                            td = row.find('td')
                            if not td:
                                continue
                            font = td.find('font', class_='spy14')
                            if not font:
                                continue

                            # IP'ni topish
                            text = font.get_text(" ", strip=True)
                            ip_match = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', text)
                            if not ip_match:
                                continue
                            ip = ip_match.group(1)

                            # Port'ni decode qilish
                            script_tag = font.find('script')
                            port = None

                            if script_tag and script_tag.string:
                                port = self._decode_port_from_script(script_tag.string, var_map)

                                # Script'dan keyin plain text port
                                ns = script_tag.next_sibling
                                if isinstance(ns, NavigableString):
                                    m = re.search(r':\s*(\d{2,5})', ns)
                                    if m:
                                        port = int(m.group(1))

                            # Oddiy :PORT formatni tekshirish
                            if not port:
                                m2 = re.search(r':\s*(\d{2,5})', text)
                                if m2:
                                    port = int(m2.group(1))

                            if port and 1 <= port <= 65535:
                                proxies.append(f"http://{ip}:{port}")
                        except Exception as e:
                            continue

                    self.proxies = proxies
                    self.last_fetch_time = current_time
                    print(f"✓ {len(proxies)} ta proxy topildi va cache'ga saqlandi")
                    return proxies

        except Exception as e:
            print(f"❌ Proxy fetch error: {str(e)}")
            return self.proxies if self.proxies else []

    def _decode_port_from_script(self, script_text: str, var_map: dict) -> Optional[int]:
        """Script ichidagi xor (^) operatsiyalarni yechadi."""
        try:
            ops = re.findall(r'([A-Za-z0-9_]+)\s*\^\s*([A-Za-z0-9_]+)', script_text)
            if not ops:
                digits = re.findall(r'\+(\d+)', script_text)
                if digits:
                    port = int(''.join(digits))
                    return port if 1 <= port <= 65535 else None
                return None

            parts = []
            for a, b in ops:
                v1 = var_map.get(a)
                v2 = var_map.get(b)

                if v1 is None:
                    m = re.search(r'(\d+)', a)
                    v1 = int(m.group(1)) if m else 0
                if v2 is None:
                    m = re.search(r'(\d+)', b)
                    v2 = int(m.group(1)) if m else 0

                val = v1 ^ v2
                parts.append(str(val))

            port_str = ''.join(parts)
            if port_str.isdigit():
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
                        return time.time() - start_time
                    return None
        except:
            return None

    async def get_working_proxies(self, max_proxies: int = 10, max_tests: int = 30) -> List[str]:
        """Ishlaydigan proxy'larni topish (parallel test bilan)"""
        # Agar working_proxies allaqachon bor bo'lsa va yangi emas bo'lsa
        if self.working_proxies:
            current_time = time.time()
            # Agar oxirgi fetch 5 daqiqadan kam bo'lsa, cache'dan foydalanish
            if (current_time - self.last_fetch_time) < self.cache_duration:
                print(f"✓ Cache'dan {len(self.working_proxies)} ta ishlaydigan proxy")
                return [p for p, _ in self.working_proxies]

        if not self.proxies:
            await self.fetch_uzbek_proxies(max_rows=max_tests)

        if not self.proxies:
            print("❌ Hech qanday proxy topilmadi")
            return []

        print(f"🔄 Proxy'lar test qilinmoqda...")
        test_proxies = self.proxies[:max_proxies * 3]
        sem = asyncio.Semaphore(12)

        async def sem_test(p):
            async with sem:
                return p, await self.test_proxy(p)

        tasks = [sem_test(p) for p in test_proxies]
        results = await asyncio.gather(*tasks)

        working = [(p, rt) for p, rt in results if rt is not None]
        working.sort(key=lambda x: x[1])
        self.working_proxies = working[:max_proxies]

        if working:
            print(f"✓ {len(working)} ta ishlaydigan proxy topildi")
            for p, rt in working[:3]:
                print(f"  • {p} ({rt:.2f}s)")
        else:
            print("❌ Hech qanday ishlaydigan proxy topilmadi")

        return [p for p, _ in self.working_proxies]


# Global ProxyManager instance
_proxy_manager = ProxyManager()


async def get_site_content(URL: str, use_proxy: bool = True) -> Optional[Any]:
    """
    URL'ga so'rov yuboradi.
    use_proxy=True bo'lsa, avval O'zbekiston proksilarini ishlatadi.
    Agar proxy ishlamasa yoki use_proxy=False bo'lsa, to'g'ridan-to'g'ri ulanadi.
    """
    print(f"\n{'=' * 60}")
    print(f"📡 So'rov: {URL}")
    print(f"{'=' * 60}")

    if use_proxy:
        # Ishlaydigan proxy'larni olish (cache'dan yoki yangi test qilish)
        proxies = await _proxy_manager.get_working_proxies(max_proxies=5)

        # Proxy bilan urinish
        if proxies:
            for i, proxy in enumerate(proxies, 1):
                try:
                    print(f"🔄 Proxy #{i} ishlatilmoqda: {proxy}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                                URL,
                                proxy=proxy,
                                ssl=False,
                                timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status == 200:
                                print(f"✓ Proxy bilan muvaffaqiyatli: {proxy}")
                                try:
                                    return await resp.json()
                                except:
                                    return await resp.text()
                            else:
                                print(f"⚠️ Status {resp.status} - boshqa proxy sinalib ko'rilmoqda...")
                except Exception as e:
                    print(f"❌ Proxy xatosi: {str(e)[:50]}")
                    continue

            print("⚠️ Hamma proxy'lar ishlamadi, to'g'ridan-to'g'ri ulanish...")
        else:
            print("⚠️ Ishlaydigan proxy topilmadi, to'g'ridan-to'g'ri ulanish...")

    # To'g'ridan-to'g'ri ulanish
    try:
        print(f"🔄 To'g'ridan-to'g'ri ulanish...")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    URL,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    print(f"✓ To'g'ridan-to'g'ri muvaffaqiyatli!")
                    try:
                        return await resp.json()
                    except:
                        return await resp.text()
                else:
                    print(f"❌ Status: {resp.status}")
                    return None
    except Exception as e:
        print(f"❌ To'g'ridan-to'g'ri so'rov xatosi: {str(e)}")
        return None


# Foydalanish misoli
async def main():
    url = "https://ishapi.mehnat.uz/api/v1/vacancies?per_page=5&salary=&vacancy_soato_code=&sort_key=created_at&nskz=213,312&page=1"

    # Proxy bilan
    result = await get_site_content(url, use_proxy=True)

    if result:
        print(f"\n✓ Natija olindi: {str(result)[:100]}...")
    else:
        print("\n❌ Natija olinmadi")


if __name__ == "__main__":
    asyncio.run(main())