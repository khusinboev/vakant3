import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


# Spys.one JavaScript port calculator
def decode_port(script_text: str) -> Optional[int]:
    """Spys.one ning obfuscated port'ini decode qilish"""
    try:
        # Script ichidagi operatsiyalarni topish
        operations = re.findall(r'(\w+)\^(\w+)', script_text)

        # Variable mapping (oddiy misol - real decode murakkab)
        var_map = {
            'Zero': 0, 'One': 1, 'Two': 2, 'Three': 3, 'Four': 4,
            'Five': 5, 'Six': 6, 'Seven': 7, 'Eight': 8, 'Nine': 9,
        }

        # Har bir digit uchun XOR
        port_str = ""
        for var1, var2 in operations:
            # Variable nomlaridan raqam olish
            num1 = parse_var(var1, var_map)
            num2 = parse_var(var2, var_map)
            if num1 is not None and num2 is not None:
                port_str += str(num1 ^ num2)

        return int(port_str) if port_str else None
    except:
        return None


def parse_var(var_name: str, var_map: dict) -> Optional[int]:
    """Variable nomidan raqam olish"""
    # SevenSevenEightFive -> 7785
    digits = re.findall(r'(Zero|One|Two|Three|Four|Five|Six|Seven|Eight|Nine)', var_name)
    if digits:
        result = ""
        for d in digits:
            result += str(var_map.get(d, 0))
        return int(result)
    return None


async def fetch_uzbek_proxies() -> List[str]:
    """Spys.one saytidan O'zbekiston proxy'larini scraping qilish"""
    proxies = []
    url = "https://spys.one/free-proxy-list/UZ/"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15, ssl=False) as resp:
                if resp.status != 200:
                    return []

                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')

                # spy1x class'li tr'larni topish
                rows = soup.find_all('tr', class_='spy1x')

                for row in rows[:20]:  # Faqat birinchi 20 ta
                    try:
                        # IP:Port bo'lgan td'ni topish
                        td = row.find('td')
                        if not td:
                            continue

                        text = td.get_text(strip=True)

                        # IP ni ajratib olish
                        ip_match = re.match(r'(\d+\.\d+\.\d+\.\d+)', text)
                        if not ip_match:
                            continue

                        ip = ip_match.group(1)

                        # Port ni script'dan decode qilish
                        script = td.find('script')
                        if script:
                            port = decode_port(script.string)
                            if port:
                                proxies.append(f"http://{ip}:{port}")
                                continue

                        # Agar script bo'lmasa, oddiy :port ni qidirish
                        port_match = re.search(r':(\d+)', text)
                        if port_match:
                            port = port_match.group(1)
                            proxies.append(f"http://{ip}:{port}")

                    except Exception:
                        continue

                return proxies

    except Exception:
        return []


async def test_proxy(proxy: str, timeout: int = 8) -> bool:
    """Proxy ishlashini tezkor test qilish"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    'https://api.ipify.org?format=json',
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False
            ) as resp:
                return resp.status == 200
    except:
        return False


async def fetch_with_proxy(url: str, proxy: str, timeout: int = 30) -> Optional[Dict]:
    """Proxy orqali API'dan ma'lumot olish"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json',
                    }
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except:
        return None


async def get_site_content(URL: str) -> Optional[Dict]:
    """
    Main function - proxy orqali API'dan ma'lumot olish
    Avval O'zbekiston proxy'larini oladi, test qiladi va ishlaydigan birinchisidan foydalanadi
    """
    print(f"Fetching proxies from spys.one...")
    proxies = await fetch_uzbek_proxies()

    if not proxies:
        print("No proxies found, trying direct connection...")
        # To'g'ridan-to'g'ri urinish
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL, ssl=False, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except:
            pass
        return None

    print(f"Found {len(proxies)} proxies, testing...")

    # Har bir proxy'ni parallel test qilish
    working_proxies = []
    test_tasks = [test_proxy(proxy) for proxy in proxies[:10]]  # Faqat 10 tasini
    test_results = await asyncio.gather(*test_tasks)

    for proxy, works in zip(proxies[:10], test_results):
        if works:
            working_proxies.append(proxy)
            print(f"Working proxy: {proxy}")

    if not working_proxies:
        print("No working proxies found")
        return None

    print(f"Testing {len(working_proxies)} working proxies with target URL...")

    # Har bir working proxy bilan API'ga urinish
    for proxy in working_proxies:
        print(f"Trying: {proxy}")
        data = await fetch_with_proxy(URL, proxy, timeout=45)
        if data:
            print(f"Success with {proxy}")
            return data

    print("All proxies failed")
    return None
