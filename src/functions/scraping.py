import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import re
import time
from typing import List, Tuple, Optional, Any
from bs4 import BeautifulSoup, NavigableString
import random


class TorManager:
    """Tor tarmoq orqali anonim ulanish."""

    def __init__(self, tor_port: int = 9050, control_port: int = 9051):
        self.tor_port = tor_port
        self.control_port = control_port
        self.tor_proxy = f"socks5://127.0.0.1:{tor_port}"

    async def test_tor_connection(self) -> bool:
        """Tor ishlayotganini tekshirish."""
        try:
            connector = ProxyConnector.from_url(self.tor_proxy)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                        'https://check.torproject.org/api/ip',
                        timeout=aiohttp.ClientTimeout(total=15),
                        ssl=False
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        is_tor = data.get('IsTor', False)
                        ip = data.get('IP', 'unknown')
                        print(f"{'✓' if is_tor else '❌'} Tor: {ip} (IsTor={is_tor})")
                        return is_tor
                    return False
        except Exception as e:
            print(f"❌ Tor xato: {str(e)[:60]}")
            return False

    async def renew_tor_circuit(self, password: str = None):
        """Tor circuit'ni yangilash (yangi IP olish)."""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', self.control_port))
                if password:
                    s.send(f'AUTHENTICATE "{password}"\r\n'.encode())
                else:
                    s.send(b'AUTHENTICATE\r\n')
                response = s.recv(1024)

                s.send(b'SIGNAL NEWNYM\r\n')
                response = s.recv(1024)
                if b'250' in response:
                    print("✓ Tor circuit yangilandi")
                    await asyncio.sleep(3)  # Yangi circuit tayyor bo'lishi uchun
                    return True
            return False
        except Exception as e:
            print(f"⚠️ Circuit yangilash xatosi: {str(e)[:50]}")
            return False


class ProxyManager:
    """O'zbekiston proxy'larini boshqarish."""

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
        self.cache_duration = 600  # 10 daqiqa
        self._initialized = True

    async def fetch_uzbek_proxies(self, max_rows: int = 100) -> List[str]:
        """Spys.one va boshqa manbalardan proxy'lar."""
        current_time = time.time()
        if self.proxies and (current_time - self.last_fetch_time) < self.cache_duration:
            return self.proxies

        print("🔄 Proxy'lar yuklanmoqda...")

        # Tor orqali spys.one'ga ulanish
        tor = TorManager()
        if await tor.test_tor_connection():
            proxies = await self._fetch_via_tor(max_rows)
            if proxies:
                self.proxies = proxies
                self.last_fetch_time = current_time
                print(f"✓ {len(proxies)} ta proxy topildi")
                return proxies

        # Agar Tor ishlamasa, oddiy ulanish
        proxies = await self._fetch_direct(max_rows)
        self.proxies = proxies
        self.last_fetch_time = current_time
        return proxies

    async def _fetch_via_tor(self, max_rows: int) -> List[str]:
        """Tor orqali proxy'larni olish."""
        url = "https://spys.one/free-proxy-list/UZ/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        try:
            connector = ProxyConnector.from_url(TorManager().tor_proxy)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, timeout=20, ssl=False) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        return self._parse_proxies(html, max_rows)
        except Exception as e:
            print(f"❌ Tor fetch error: {str(e)[:50]}")
        return []

    async def _fetch_direct(self, max_rows: int) -> List[str]:
        """To'g'ridan-to'g'ri proxy'larni olish."""
        url = "https://spys.one/free-proxy-list/UZ/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=20) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        return self._parse_proxies(html, max_rows)
        except Exception as e:
            print(f"❌ Direct fetch error: {str(e)[:50]}")
        return []

    def _parse_proxies(self, html: str, max_rows: int) -> List[str]:
        """HTML'dan proxy'larni parse qilish."""
        soup = BeautifulSoup(html, 'html.parser')
        var_assigns = re.findall(r'var\s+([A-Za-z0-9_]+)\s*=\s*(\d+);', html)
        var_map = {name: int(val) for name, val in var_assigns}

        proxies = []
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
                    port = self._decode_port(script_tag.string, var_map)

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

        return proxies

    def _decode_port(self, script_text: str, var_map: dict) -> Optional[int]:
        """Port obfuskatsiyasini yechish."""
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
                v1 = var_map.get(a, 0)
                v2 = var_map.get(b, 0)

                if v1 == 0:
                    m = re.search(r'(\d+)', a)
                    v1 = int(m.group(1)) if m else 0
                if v2 == 0:
                    m = re.search(r'(\d+)', b)
                    v2 = int(m.group(1)) if m else 0

                parts.append(str(v1 ^ v2))

            port_str = ''.join(parts)
            if port_str.isdigit():
                port = int(port_str)
                return port if 1 <= port <= 65535 else None
            return None
        except Exception:
            return None

    async def test_proxy(self, proxy: str, timeout: int = 10) -> Optional[float]:
        """Proxy'ni test qilish."""
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        'http://api.ipify.org?format=json',
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        ssl=False
                ) as resp:
                    if resp.status == 200:
                        return time.time() - start_time
        except Exception:
            pass
        return None

    async def get_working_proxies(self, max_proxies: int = 10, max_tests: int = 50) -> List[str]:
        """Ishlaydigan proxy'larni topish."""
        if self.working_proxies:
            current_time = time.time()
            if (current_time - self.last_fetch_time) < self.cache_duration:
                return [p for p, _ in self.working_proxies]

        if not self.proxies:
            await self.fetch_uzbek_proxies(max_rows=max_tests)

        if not self.proxies:
            return []

        print(f"🔄 {min(len(self.proxies), max_tests)} ta proxy test...")
        test_proxies = self.proxies[:max_tests]
        sem = asyncio.Semaphore(20)

        async def sem_test(p):
            async with sem:
                return p, await self.test_proxy(p)

        tasks = [sem_test(p) for p in test_proxies]
        results = await asyncio.gather(*tasks)

        working = [(p, rt) for p, rt in results if rt is not None]
        working.sort(key=lambda x: x[1])
        self.working_proxies = working[:max_proxies]

        if working:
            print(f"✓ {len(working)} ta ishlaydigan proxy")
            for p, rt in working[:3]:
                print(f"  • {p} ({rt:.2f}s)")

        return [p for p, _ in self.working_proxies]


_proxy_manager = ProxyManager()
_tor_manager = TorManager()


async def get_site_content(
        URL: str,
        use_tor: bool = True,
        use_uz_proxy: bool = True,
        max_retries: int = 3
) -> Optional[Any]:
    """
    URL'ga so'rov yuboradi.

    Strategiya:
    1. Tor + O'zbekiston proxy (eng yaxshi variyant)
    2. Faqat Tor
    3. Faqat O'zbekiston proxy
    4. To'g'ridan-to'g'ri
    """
    print(f"\n{'=' * 60}")
    print(f"📡 {URL}")
    print(f"{'=' * 60}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7',
        'Referer': 'https://mehnat.uz/',
        'Origin': 'https://mehnat.uz',
    }

    # Strategiya 1: Tor + UZ Proxy (Tor -> UZ Proxy -> Target)
    if use_tor and use_uz_proxy:
        print(f"\n🎯 Strategiya 1: Tor + UZ Proxy")
        tor_ok = await _tor_manager.test_tor_connection()

        if tor_ok:
            uz_proxies = await _proxy_manager.get_working_proxies(max_proxies=5)

            for i, uz_proxy in enumerate(uz_proxies[:3], 1):
                try:
                    print(f"🔄 Urinish {i}: Tor -> {uz_proxy} -> Target")

                    # Tor connector orqali UZ proxy'ga ulanish
                    connector = ProxyConnector.from_url(_tor_manager.tor_proxy)

                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                                URL,
                                proxy=uz_proxy,  # UZ proxy
                                headers=headers,
                                ssl=False,
                                timeout=aiohttp.ClientTimeout(total=20)
                        ) as resp:
                            if resp.status == 200:
                                print(f"✓ Muvaffaqiyatli!")
                                try:
                                    return await resp.json()
                                except:
                                    return await resp.text()
                except Exception as e:
                    print(f"❌ Xato: {str(e)[:50]}")
                    continue

    # Strategiya 2: Faqat Tor
    if use_tor:
        print(f"\n🎯 Strategiya 2: Faqat Tor")
        tor_ok = await _tor_manager.test_tor_connection()

        if tor_ok:
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        print(f"🔄 Circuit yangilanmoqda...")
                        await _tor_manager.renew_tor_circuit()

                    print(f"🔄 Tor urinish {attempt + 1}/{max_retries}")
                    connector = ProxyConnector.from_url(_tor_manager.tor_proxy)

                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                                URL,
                                headers=headers,
                                ssl=False,
                                timeout=aiohttp.ClientTimeout(total=20)
                        ) as resp:
                            if resp.status == 200:
                                print(f"✓ Tor bilan muvaffaqiyat!")
                                try:
                                    return await resp.json()
                                except:
                                    return await resp.text()
                except Exception as e:
                    print(f"❌ Xato: {str(e)[:50]}")
                    await asyncio.sleep(2)

    # Strategiya 3: Faqat UZ Proxy
    if use_uz_proxy:
        print(f"\n🎯 Strategiya 3: Faqat UZ Proxy")
        uz_proxies = await _proxy_manager.get_working_proxies(max_proxies=10)

        for i, proxy in enumerate(uz_proxies[:5], 1):
            try:
                print(f"🔄 Proxy {i}: {proxy}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            URL,
                            proxy=proxy,
                            headers=headers,
                            ssl=False,
                            timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status == 200:
                            print(f"✓ Muvaffaqiyat!")
                            try:
                                return await resp.json()
                            except:
                                return await resp.text()
            except Exception as e:
                print(f"❌ Xato: {str(e)[:50]}")
                continue

    # Strategiya 4: To'g'ridan-to'g'ri (oxirgi imkoniyat)
    print(f"\n🎯 Strategiya 4: To'g'ridan-to'g'ri")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    URL,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    print(f"✓ To'g'ri ulanish ishladi!")
                    try:
                        return await resp.json()
                    except:
                        return await resp.text()
    except Exception as e:
        print(f"❌ Xato: {str(e)[:50]}")

    print(f"\n❌ Barcha strategiyalar muvaffaqiyatsiz")
    return None


# Test
async def main():
    url = "https://ishapi.mehnat.uz/api/v1/vacancies?per_page=5&salary=&vacancy_soato_code=&sort_key=created_at&nskz=213,312&page=1"

    result = await get_site_content(url, use_tor=True, use_uz_proxy=True)

    if result:
        print(f"\n✅ Natija olindi!")
        if isinstance(result, dict):
            print(f"Keys: {list(result.keys())[:5]}")
    else:
        print(f"\n❌ Natija yo'q")


if __name__ == "__main__":
    asyncio.run(main())