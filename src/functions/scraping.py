# Yangi / o'zgartirilgan ProxyManager (to'liq replacement)
import asyncio
import aiohttp
import re
import time
from typing import List, Tuple, Optional, Any
from bs4 import BeautifulSoup, NavigableString


async def get_site_content(URL: str) -> Optional[Any]:
    """
    URL'ga so'rov yuboradi.
    Avval ishlaydigan O'zbekiston proksilarini ProxyManager orqali oladi.
    Agar hech biri ishlamasa — to'g'ridan-to'g'ri ulanadi.
    """
    pm = ProxyManager()
    proxies = await pm.get_working_proxies(max_proxies=5)

    # 1) agar ishlaydigan proxy bo'lsa, ulardan birini tanlab ishlatamiz
    if proxies:
        for proxy in proxies:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(URL, proxy=proxy, ssl=False, timeout=10) as resp:
                        if resp.status == 200:
                            try:
                                return await resp.json()
                            except:
                                return await resp.text()
            except Exception:
                continue

    # 2) agar hamma proxy ishlamasa, to'g'ridan-to'g'ri ulanib ko'ramiz
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(URL, ssl=False, timeout=10) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except:
                        return await resp.text()
    except Exception as e:
        print(f"Direct request error: {e}")
        return None

class ProxyManager:
    """O'zbekiston proxy'larini boshqarish va spys.one obfuskatsiyasini yechish."""
    def __init__(self):
        self.proxies: List[str] = []
        self.working_proxies: List[Tuple[str, float]] = []
        self.last_fetch_time = 0
        self.cache_duration = 300  # 5 daqiqa

    async def fetch_uzbek_proxies(self, max_rows: int = 50) -> List[str]:
        """Spys.one dan O'zbekiston proxy'larini o'qish va portlarni decode qilish."""
        current_time = time.time()
        if self.proxies and (current_time - self.last_fetch_time) < self.cache_duration:
            return self.proxies

        url = "https://spys.one/free-proxy-list/UZ/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        proxies: List[str] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=20) as resp:
                    if resp.status != 200:
                        print(f"Spys.one response status: {resp.status}")
                        return []
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Sahifadagi barcha var assignlarni yig'ib olamiz (var NAME=1234;)
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

                            # raw html ichidan IP va scriptni olish
                            # IP: odatda birinchi 4 oktet
                            text = font.get_text(" ", strip=True)
                            ip_match = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', text)
                            if not ip_match:
                                continue
                            ip = ip_match.group(1)

                            # 1) agar font ichida <script> bo'lsa, uni o'qiymiz va decode qilamiz
                            script_tag = font.find('script')
                            port = None
                            if script_tag and script_tag.string:
                                port = self._decode_port_from_script(script_tag.string, var_map)

                                # Ba'zan script tagdan keyin plain text ko'rinishida ":8026" bo'ladi
                                # script_tag.next_sibling yoki .next_element orqali tekshiramiz
                                ns = script_tag.next_sibling
                                if isinstance(ns, NavigableString):
                                    m = re.search(r':\s*(\d{2,5})', ns)
                                    if m:
                                        port = int(m.group(1))

                            # 2) agar yuqoridagi usul ishlamasa, text ichidagi oddiy :PORT dan izlaymiz
                            if not port:
                                m2 = re.search(r':\s*(\d{2,5})', text)
                                if m2:
                                    port = int(m2.group(1))

                            # port validligini tekshiramiz
                            if port and 1 <= port <= 65535:
                                proxies.append(f"http://{ip}:{port}")
                        except Exception:
                            continue

                    self.proxies = proxies
                    self.last_fetch_time = current_time
                    print(f"✓ {len(proxies)} ta proxy topildi (cache yangilandi).")
                    return proxies

        except Exception as e:
            print(f"Proxy fetch error: {str(e)}")
            return []

    def _decode_port_from_script(self, script_text: str, var_map: dict) -> Optional[int]:
        """
        Script ichidagi xor (^) operatsiyalarni yechadi.
        Misol: document.write(":"+(A^B)+(C^D)+... )
        var_map sahifadagi var NAME=123; juftliklarini oldindan olgan bo'lishi kerak.
        """
        try:
            # script ichidagi (X^Y) yoki X^Y ni topamiz (avval function ichidagi qismi)
            ops = re.findall(r'([A-Za-z0-9_]+)\s*\^\s*([A-Za-z0-9_]+)', script_text)
            if not ops:
                # ba'zan inline raqamlar bo'lishi mumkin: ("+"+123)
                digits = re.findall(r'\+(\d+)', script_text)
                if digits:
                    port = int(''.join(digits))
                    return port if 1 <= port <= 65535 else None
                return None

            parts = []
            for a, b in ops:
                v1 = var_map.get(a)
                v2 = var_map.get(b)
                # Agar var sahifada topilmagan bo'lsa, o'zgaruvchi nomi ichidan raqamlarni ajratib ko'rish
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
                ) as resp:
                    if resp.status == 200:
                        return time.time() - start_time
                    return None
        except:
            return None

    async def get_working_proxies(self, max_proxies: int = 10, max_tests: int = 30) -> List[str]:
        """Ishlaydigan proxy'larni topish (parallel test bilan)"""
        if not self.proxies:
            await self.fetch_uzbek_proxies(max_rows=max_tests)

        if not self.proxies:
            return []

        test_proxies = self.proxies[: max_proxies * 3]
        # Parallel test — lekin haddan ortiq yuklamaslik uchun semaphore foydalanish mumkin.
        sem = asyncio.Semaphore(12)  # bir vaqtda test qilinadigan limit

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

        return [p for p, _ in self.working_proxies]
