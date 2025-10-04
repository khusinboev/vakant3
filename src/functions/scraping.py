import asyncio
import aiohttp
import re
import time
from typing import List, Tuple, Optional, Any
from bs4 import BeautifulSoup, NavigableString


class ProxyManager:
    """O'zbekiston proxy'larini boshqarish va spys.one obfuskatsiyasini yechish."""

    _instance = None

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
        self.cache_duration = 300
        self._initialized = True

    async def fetch_uzbek_proxies(self, max_rows: int = 100) -> List[str]:
        """Spys.one dan O'zbekiston proxy'larini o'qish."""
        current_time = time.time()
        if self.proxies and (current_time - self.last_fetch_time) < self.cache_duration:
            print(f"✓ Cache'dan {len(self.proxies)} ta proxy ishlatilmoqda")
            return self.proxies

        url = "https://spys.one/free-proxy-list/UZ/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7',
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

                            text = font.get_text(" ", strip=True)
                            ip_match = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', text)
                            if not ip_match:
                                continue
                            ip = ip_match.group(1)

                            script_tag = font.find('script')
                            port = None

                            if script_tag and script_tag.string:
                                port = self._decode_port_from_script(script_tag.string, var_map)

                                ns = script_tag.next_sibling
                                if isinstance(ns, NavigableString):
                                    m = re.search(r':\s*(\d{2,5})', ns)
                                    if m:
                                        port = int(m.group(1))

                            if not port:
                                m2 = re.search(r':\s*(\d{2,5})', text)
                                if m2:
                                    port = int(m2.group(1))

                            if port and 1 <= port <= 65535:
                                proxies.append(f"http://{ip}:{port}")
                        except Exception:
                            continue

                    self.proxies = proxies
                    self.last_fetch_time = current_time
                    print(f"✓ {len(proxies)} ta proxy topildi")
                    return proxies

        except Exception as e:
            print(f"❌ Proxy fetch error: {str(e)}")
            return self.proxies if self.proxies else []

    def _decode_port_from_script(self, script_text: str, var_map: dict) -> Optional[int]:
        """Script ichidagi xor operatsiyalarni yechadi."""
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

    async def test_proxy(self, proxy: str, test_url: str = None, timeout: int = 10) -> Optional[float]:
        """Proxy'ni test qilish."""
        if test_url is None:
            test_url = 'http://api.ipify.org?format=json'

        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        test_url,
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        ssl=False
                ) as resp:
                    if resp.status == 200:
                        return time.time() - start_time
                    return None
        except Exception:
            return None

    async def get_working_proxies(self, max_proxies: int = 10, max_tests: int = 50, test_url: str = None) -> List[str]:
        """Ishlaydigan proxy'larni topish."""
        if self.working_proxies:
            current_time = time.time()
            if (current_time - self.last_fetch_time) < self.cache_duration:
                print(f"✓ Cache'dan {len(self.working_proxies)} ta proxy")
                return [p for p, _ in self.working_proxies]

        if not self.proxies:
            await self.fetch_uzbek_proxies(max_rows=max_tests)

        if not self.proxies:
            print("❌ Proxy topilmadi")
            return []

        print(f"🔄 {len(self.proxies[:max_tests])} ta proxy test qilinmoqda...")
        test_proxies = self.proxies[:max_tests]
        sem = asyncio.Semaphore(15)

        async def sem_test(p):
            async with sem:
                result = await self.test_proxy(p, test_url=test_url)
                if result:
                    print(f"  ✓ {p} ({result:.2f}s)")
                return p, result

        tasks = [sem_test(p) for p in test_proxies]
        results = await asyncio.gather(*tasks)

        working = [(p, rt) for p, rt in results if rt is not None]
        working.sort(key=lambda x: x[1])
        self.working_proxies = working[:max_proxies]

        if working:
            print(f"✓ {len(working)} ta ishlaydigan proxy topildi")
        else:
            print("❌ Ishlaydigan proxy yo'q")

        return [p for p, _ in self.working_proxies]


_proxy_manager = ProxyManager()


async def get_site_content(URL: str, use_proxy: bool = True, max_retries: int = 3) -> Optional[Any]:
    """
    URL'ga so'rov yuboradi.
    """
    print(f"\n{'=' * 60}")
    print(f"📡 {URL}")
    print(f"{'=' * 60}")

    # Browser kabi headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://mehnat.uz/',
        'Origin': 'https://mehnat.uz',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }

    # Avval proxy'siz sinab ko'ramiz (tezroq)
    for attempt in range(max_retries):
        try:
            print(f"🔄 To'g'ri ulanish (urinish {attempt + 1}/{max_retries})...")
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        URL,
                        headers=headers,
                        ssl=False,
                        timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    print(f"📊 Status: {resp.status}")

                    if resp.status == 200:
                        print(f"✓ Muvaffaqiyatli!")
                        content_type = resp.headers.get('Content-Type', '')

                        if 'application/json' in content_type:
                            return await resp.json()
                        else:
                            return await resp.text()
                    elif resp.status == 403:
                        print(f"⚠️ 403 Forbidden - Proxy kerak bo'lishi mumkin")
                        break  # Proxy'ga o'tish
                    elif resp.status == 503:
                        print(f"⚠️ 503 Service Unavailable - Cloudflare himoyasi")
                        break
                    else:
                        print(f"⚠️ Status {resp.status}")
                        await asyncio.sleep(1)

        except asyncio.TimeoutError:
            print(f"⏱️ Timeout - {attempt + 1}/{max_retries}")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Xato: {str(e)[:100]}")
            await asyncio.sleep(1)

    # Agar to'g'ri ulanish ishlamasa va proxy kerak bo'lsa
    if use_proxy:
        print(f"\n🔄 Proxy'lar orqali urinish...")
        proxies = await _proxy_manager.get_working_proxies(max_proxies=10, max_tests=50)

        if proxies:
            for i, proxy in enumerate(proxies, 1):
                try:
                    print(f"🔄 Proxy #{i}: {proxy}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                                URL,
                                proxy=proxy,
                                headers=headers,
                                ssl=False,
                                timeout=aiohttp.ClientTimeout(total=15)
                        ) as resp:
                            print(f"📊 Status: {resp.status}")

                            if resp.status == 200:
                                print(f"✓ Proxy bilan muvaffaqiyat: {proxy}")
                                content_type = resp.headers.get('Content-Type', '')

                                if 'application/json' in content_type:
                                    return await resp.json()
                                else:
                                    return await resp.text()
                            else:
                                print(f"⚠️ Status {resp.status}")

                except Exception as e:
                    print(f"❌ Proxy xato: {str(e)[:50]}")
                    continue

    print(f"\n❌ Hamma urinishlar muvaffaqiyatsiz")
    return None


# Test
async def main():
    url = "https://ishapi.mehnat.uz/api/v1/vacancies?per_page=5&salary=&vacancy_soato_code=&sort_key=created_at&nskz=213,312&page=1"

    result = await get_site_content(url, use_proxy=True)

    if result:
        print(f"\n✅ Natija olindi!")
        if isinstance(result, dict):
            print(f"Keys: {list(result.keys())}")
    else:
        print(f"\n❌ Natija yo'q")


if __name__ == "__main__":
    asyncio.run(main())