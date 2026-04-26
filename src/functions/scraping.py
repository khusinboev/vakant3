import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import re
import time
from typing import List, Tuple, Optional, Any
from bs4 import BeautifulSoup, NavigableString
import random
import logging

logger = logging.getLogger(__name__)

_TOR_PROXY = "socks5://127.0.0.1:9050"
_TOR_CONTROL_PORT = 9051
_TOR_CHECK_TTL = 60.0  # Tor holati necha soniya keshlanadi

_tor_available: Optional[bool] = None
_tor_checked_at: float = 0.0


async def _check_tor() -> bool:
    """Tor mavjudligini tekshirish, natijani 60 soniya keshlash."""
    global _tor_available, _tor_checked_at
    now = asyncio.get_event_loop().time()
    if _tor_available is not None and (now - _tor_checked_at) < _TOR_CHECK_TTL:
        return _tor_available

    try:
        connector = ProxyConnector.from_url(_TOR_PROXY)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                'https://check.torproject.org/api/ip',
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _tor_available = bool(data.get('IsTor', False))
                else:
                    _tor_available = False
    except Exception:
        _tor_available = False

    _tor_checked_at = asyncio.get_event_loop().time()
    logger.info("Tor: %s", "mavjud ✓" if _tor_available else "mavjud emas")
    return _tor_available


async def _renew_tor_circuit() -> bool:
    """Stem orqali yangi Tor circuit olish."""
    try:
        from stem import Signal
        from stem.control import Controller

        def _do_renew():
            with Controller.from_port(port=_TOR_CONTROL_PORT) as c:
                c.authenticate()
                c.signal(Signal.NEWNYM)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_renew)
        await asyncio.sleep(1)
        global _tor_available, _tor_checked_at
        _tor_available = True
        _tor_checked_at = asyncio.get_event_loop().time()
        logger.info("Tor circuit yangilandi ✓")
        return True
    except Exception as e:
        logger.warning("_renew_tor_circuit xato: %s", e)
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

        logger.debug("Proxy'lar yuklanmoqda...")

        if await _check_tor():
            proxies = await self._fetch_via_tor(max_rows)
            if proxies:
                self.proxies = proxies
                self.last_fetch_time = current_time
                logger.debug("%d ta proxy topildi", len(proxies))
                return proxies

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
            connector = ProxyConnector.from_url(_TOR_PROXY)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, timeout=20, ssl=False) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        return self._parse_proxies(html, max_rows)
        except Exception as e:
            logger.debug("Tor fetch error: %s", str(e)[:50])
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
            logger.debug("Direct fetch error: %s", str(e)[:50])
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
            logger.debug("%d ta ishlaydigan proxy topildi", len(working))

        return [p for p, _ in self.working_proxies]


_proxy_manager = ProxyManager()


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
    logger.debug("get_site_content: %s", URL)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7',
        'Referer': 'https://mehnat.uz/',
        'Origin': 'https://mehnat.uz',
    }

    # Strategiya 1: Tor + UZ Proxy
    if use_tor and use_uz_proxy:
        tor_ok = await _check_tor()
        if tor_ok:
            uz_proxies = await _proxy_manager.get_working_proxies(max_proxies=5)
            for uz_proxy in uz_proxies[:3]:
                try:
                    connector = ProxyConnector.from_url(_TOR_PROXY)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                                URL, proxy=uz_proxy, headers=headers,
                                ssl=False, timeout=aiohttp.ClientTimeout(total=20)
                        ) as resp:
                            if resp.status == 200:
                                try:
                                    return await resp.json()
                                except Exception:
                                    return await resp.text()
                except Exception as e:
                    logger.debug("S1 xato: %s", str(e)[:50])
                    continue

    # Strategiya 2: Faqat Tor
    if use_tor:
        tor_ok = await _check_tor()
        if tor_ok:
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        await _renew_tor_circuit()
                    connector = ProxyConnector.from_url(_TOR_PROXY)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                                URL, headers=headers, ssl=False,
                                timeout=aiohttp.ClientTimeout(total=20)
                        ) as resp:
                            if resp.status == 200:
                                try:
                                    return await resp.json()
                                except Exception:
                                    return await resp.text()
                except Exception as e:
                    logger.debug("S2 xato: %s", str(e)[:50])
                    await asyncio.sleep(2)

    # Strategiya 3: Faqat UZ Proxy
    if use_uz_proxy:
        uz_proxies = await _proxy_manager.get_working_proxies(max_proxies=10)
        for proxy in uz_proxies[:5]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            URL, proxy=proxy, headers=headers,
                            ssl=False, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status == 200:
                            try:
                                return await resp.json()
                            except Exception:
                                return await resp.text()
            except Exception as e:
                logger.debug("S3 xato: %s", str(e)[:50])
                continue

    # Strategiya 4: To'g'ridan-to'g'ri
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    URL, headers=headers, ssl=False,
                    timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except Exception:
                        return await resp.text()
    except Exception as e:
        logger.debug("S4 xato: %s", str(e)[:50])

    logger.warning("get_site_content: barcha strategiyalar muvaffaqiyatsiz — %s", URL)
    return None


async def get_site_content_direct(url: str) -> Optional[Any]:
    """To'g'ridan-to'g'ri API so'rovi. Proxy yoki Tor ishlatilmaydi."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7',
        'Referer': 'https://mehnat.uz/',
        'Origin': 'https://mehnat.uz',
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning("get_site_content_direct: HTTP %s — %s", resp.status, url)
                return None
    except Exception as e:
        logger.error("get_site_content_direct: xato %s — %s", url, e)
        return None


_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7',
    'Referer': 'https://mehnat.uz/',
    'Origin': 'https://mehnat.uz',
}


async def get_site_content_tor(url: str) -> Optional[Any]:
    """
    Tor orqali API so'rovi — geo-cheklovni aylanib o'tish.
    403/429 kelsa circuit yangilab bir marta qayta urinadi.
    """
    if not await _check_tor():
        logger.debug("get_site_content_tor: Tor mavjud emas")
        return None

    for attempt in range(2):
        try:
            if attempt > 0:
                logger.info("get_site_content_tor: circuit yangilanmoqda...")
                renewed = await _renew_tor_circuit()
                if not renewed:
                    return None

            connector = ProxyConnector.from_url(_TOR_PROXY)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    url,
                    headers=_HEADERS,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status in (403, 429) and attempt == 0:
                        logger.warning("get_site_content_tor: HTTP %s — circuit yangilanadi", resp.status)
                        continue
                    logger.warning("get_site_content_tor: HTTP %s — %s", resp.status, url)
                    return None
        except Exception as e:
            logger.error("get_site_content_tor: urinish %d xato: %s", attempt + 1, e)
            if attempt == 0:
                continue

    return None


async def fetch(url: str) -> Optional[Any]:
    """
    Asosiy so'rov funksiyasi (tez + geo-bypass):
    1. To'g'ridan-to'g'ri (10s)
    2. Tor orqali (20s) — faqat to'g'ri yo'l ishlamasa
    """
    result = await get_site_content_direct(url)
    if result is not None:
        return result
    logger.info("fetch: to'g'ri yo'l ishlamadi, Tor sinash... url=%s", url)
    return await get_site_content_tor(url)


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