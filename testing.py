import asyncio
import json
import random
import time
from playwright.async_api import async_playwright

# USER AGENTS
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

# O'ZBEKISTON PROXY'LAR - bularni yangilab turing!
# Quyidagi saytlardan oling:
# 1. https://proxyscrape.com/free-proxy-list/uzbekistan
# 2. https://www.ditatompel.com/proxy/country/uz
# 3. https://spys.one/free-proxy-list/UZ/

UZBEK_PROXIES = [
    # Misol format (hozircha test uchun):
    # {'server': 'http://IP:PORT'},
    {'server': 'http://195.158.10.99:8080'},
    # Bepul proxy'lar tez o'zgaradi, shuning uchun har doim yangi ro'yxat oling!
]

# GLOBAL BEPUL PROXY'LAR (test uchun)
GLOBAL_PROXIES = [
    # Bu yerga https://free-proxy-list.net dan oling
    # {'server': 'http://IP:PORT'},
]

# TOR
TOR_PROXY = {'server': 'socks5://127.0.0.1:9050'}


async def fetch_uzbek_proxies():
    """
    ProxyScrape API orqali O'zbekiston proxy'larini olish
    """
    print("🔍 O'zbekiston proxy'larini qidiryapman...")
    try:
        import aiohttp
        url = "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=5000&country=UZ&ssl=all&anonymity=all"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    text = await response.text()
                    proxies = []
                    for line in text.strip().split('\n'):
                        if line and ':' in line:
                            ip, port = line.split(':')
                            proxies.append({'server': f'http://{ip.strip()}:{port.strip()}'})

                    if proxies:
                        print(f"✅ {len(proxies)} ta UZ proxy topildi!")
                        return proxies[:10]  # Faqat birinchi 10 ta
                    else:
                        print("⚠️ UZ proxy topilmadi")
                        return []
    except ImportError:
        print("⚠️ aiohttp o'rnatilmagan: pip install aiohttp")
        return []
    except Exception as e:
        print(f"⚠️ Proxy olishda xatolik: {e}")
        return []


async def test_proxy(proxy_config, test_url="https://api.ipify.org?format=json"):
    """
    Proxy ishlashini tezkor test qilish
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy_config
            )
            page = await browser.new_page()
            await page.goto(test_url, timeout=10000)
            ip = await page.evaluate('() => document.body.innerText')
            await browser.close()
            return True, ip
    except Exception as e:
        return False, str(e)[:50]


async def scrape_with_proxy(target_url, api_url, proxy_config, proxy_name="Unknown"):
    """
    Proxy orqali scraping
    """
    start = time.time()
    print(f"\n{'=' * 70}")
    print(f"🧪 TEST: {proxy_name}")
    print(f"{'=' * 70}")

    async with async_playwright() as p:
        try:
            # Browser launch
            launch_opts = {
                'headless': True,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            }

            if proxy_config:
                launch_opts['proxy'] = proxy_config
                print(f"🌐 Proxy: {proxy_config['server']}")

            browser = await p.chromium.launch(**launch_opts)

            # Context
            user_agent = random.choice(USER_AGENTS)
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='uz-UZ',  # O'zbek locale
                timezone_id='Asia/Tashkent',
                extra_http_headers={
                    'Accept-Language': 'uz-UZ,uz;q=0.9,en;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'DNT': '1',
                }
            )

            page = await context.new_page()

            # Anti-detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)

            # IP tekshirish
            if proxy_config:
                try:
                    ip_page = await context.new_page()
                    await ip_page.goto('https://api.ipify.org?format=json', timeout=8000)
                    ip_data = await ip_page.evaluate('() => document.body.innerText')
                    print(f"📍 IP: {ip_data}")
                    await ip_page.close()
                except:
                    print("⚠️ IP tekshirib bo'lmadi")

            # Asosiy sahifa
            print(f"📡 Ulanmoqda: {target_url}")
            await page.goto(target_url, timeout=45000, wait_until='domcontentloaded')
            print(f"✅ Sahifa yuklandi! ({time.time() - start:.1f}s)")

            # Random delay
            await asyncio.sleep(random.uniform(1.5, 3))

            # API
            print(f"📥 API: {api_url}")
            data = await page.evaluate(f"""
                async () => {{
                    try {{
                        const res = await fetch('{api_url}');
                        if (!res.ok) return {{ error: 'HTTP ' + res.status }};
                        return await res.json();
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
            """)

            await context.close()
            await browser.close()

            # Natija
            if data and 'error' not in data:
                elapsed = time.time() - start
                print(f"✅ SUCCESS! Ma'lumot olindi! ({elapsed:.1f}s)")
                print(f"📊 Data sample: {str(data)[:100]}...")
                return {'success': True, 'data': data, 'time': elapsed, 'proxy': proxy_name}
            else:
                print(f"❌ API Error: {data.get('error', 'Unknown')}")
                return {'success': False, 'error': 'API failed', 'proxy': proxy_name}

        except Exception as e:
            elapsed = time.time() - start
            error_msg = str(e)[:80]
            print(f"❌ FAILED: {error_msg} ({elapsed:.1f}s)")
            return {'success': False, 'error': error_msg, 'time': elapsed, 'proxy': proxy_name}


async def main():
    """
    O'zbekiston IP bilan bypass test
    """
    print("🇺🇿" * 35)
    print("🚀 O'ZBEKISTON IP BYPASS - ULTIMATE TEST")
    print("🇺🇿" * 35)

    # SIZNING SAYT URL'LARINGIZ!
    TARGET_URL = "https://ish.mehnat.uz/vacancies"
    API_URL = "https://api.mehnat.uz/api/v1/vacancies?per_page=5&isVisible=true&page=1"

    print(f"\n🎯 Target: {TARGET_URL}")
    print(f"🎯 API: {API_URL}\n")

    results = []

    # 1. Bloklangan IP (baseline)
    print("\n1️⃣ BLOKLANGAN IP (baseline)")
    result = await scrape_with_proxy(TARGET_URL, API_URL, None, "Direct (Blocked)")
    results.append(result)
    await asyncio.sleep(2)

    # 2. O'zbekiston proxy'larini olish va sinash
    print("\n2️⃣ O'ZBEKISTON PROXY'LARI")
    uz_proxies = await fetch_uzbek_proxies()

    if uz_proxies:
        # Har bir UZ proxy'ni sinash
        for i, proxy in enumerate(uz_proxies[:5], 1):  # Faqat 5 tasini sinash
            print(f"\n🇺🇿 UZ Proxy #{i}")
            # Avval tezkor test
            works, info = await test_proxy(proxy)
            if works:
                print(f"✅ Proxy ishlayapti: {info}")
                result = await scrape_with_proxy(TARGET_URL, API_URL, proxy, f"UZ-Proxy-{i}")
                results.append(result)

                # Agar muvaffaqiyatli bo'lsa, to'xtatamiz!
                if result['success']:
                    print("\n🎉🎉🎉 MUVAFFAQIYAT! Bypass qilindi! 🎉🎉🎉")
                    break
            else:
                print(f"❌ Proxy ishlamayapti: {info}")

            await asyncio.sleep(2)
    else:
        print("⚠️ O'zbekiston proxy topilmadi")
        print("💡 Qo'lda quyidagi saytlardan proxy qo'shing:")
        print("   - https://proxyscrape.com/free-proxy-list/uzbekistan")
        print("   - https://www.ditatompel.com/proxy/country/uz")

    # 3. Manual UZ proxy (agar UZBEK_PROXIES to'ldirilgan bo'lsa)
    if UZBEK_PROXIES:
        print("\n3️⃣ MANUAL O'ZBEKISTON PROXY'LAR")
        for i, proxy in enumerate(UZBEK_PROXIES, 1):
            result = await scrape_with_proxy(TARGET_URL, API_URL, proxy, f"Manual-UZ-{i}")
            results.append(result)
            if result['success']:
                print("\n🎉 BYPASS QILINDI!")
                break
            await asyncio.sleep(2)

    # FINAL NATIJALAR
    print("\n\n" + "=" * 70)
    print("📊 FINAL NATIJALAR:")
    print("=" * 70)

    success_count = sum(1 for r in results if r['success'])

    for i, result in enumerate(results, 1):
        status = "✅ MUVAFFAQIYAT" if result['success'] else "❌ MUVAFFAQIYATSIZ"
        proxy_name = result.get('proxy', 'Unknown')
        time_taken = result.get('time', 0)
        print(f"{i}. {proxy_name:25} : {status:20} ({time_taken:.1f}s)")

    print("=" * 70)
    print(f"📈 Umumiy: {success_count}/{len(results)} muvaffaqiyatli")

    if success_count > 0:
        print("\n🎊 TABRIKLAYMAN! Saytingiz bypass qilindi!")
        print("💡 Bu degani:")
        print("   ✅ Sizning IP blok mexanizmi ishlayapti")
        print("   ✅ Lekin O'zbekiston IP'lari orqali kirishsa bo'ladi")
        print("   🔐 Qo'shimcha himoya kerak bo'lsa:")
        print("      - Rate limiting qo'shing")
        print("      - CAPTCHA qo'shing")
        print("      - User-Agent tekshiring")
        print("      - Browser fingerprint tekshiring")
    else:
        print("\n🛡️ AJOYIB! Saytingiz juda mustahkam!")
        print("💪 Hech qanday usul ishlamadi!")
        print("   Ehtimol barcha proxy'lar ham bloklangan")
        print("   yoki proxy'lar ishlamayapti")

    print("=" * 70)


if __name__ == "__main__":
    # aiohttp o'rnatish haqida eslatma
    print("📦 Kerakli paket: pip install aiohttp playwright")
    print("💡 Agar aiohttp bo'lmasa, faqat manual proxy'lar sinab ko'riladi\n")

    asyncio.run(main())