import asyncio
import json
import random
import time
from playwright.async_api import async_playwright

# 1. USER AGENT ROTATION
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

# 2. BEPUL PROXY'LAR (misol - https://free-proxy-list.net dan oling)
FREE_PROXIES = [
    # Misol formatlar:
    # {'server': 'http://proxy-ip:port'},
    # {'server': 'socks5://proxy-ip:port'},
]

# 3. TOR KONFIGURATSIYASI
TOR_PROXY = {
    'server': 'socks5://127.0.0.1:9050'
}

# 4. VPN KONFIGURATSIYASI (agar bor bo'lsa)
VPN_PROXY = {
    # Misol: ProtonVPN, NordVPN SOCKS5
    # 'server': 'socks5://vpn-server:1080',
    # 'username': 'your_username',
    # 'password': 'your_password'
}


async def get_current_ip(proxy=None):
    """IP manzilni tekshirish"""
    async with async_playwright() as p:
        launch_opts = {'headless': True}
        if proxy:
            launch_opts['proxy'] = proxy

        browser = await p.chromium.launch(**launch_opts)
        page = await browser.new_page()
        try:
            await page.goto('https://api.ipify.org?format=json', timeout=15000)
            ip_text = await page.evaluate('() => document.body.innerText')
            ip_data = json.loads(ip_text)
            await browser.close()
            return ip_data['ip']
        except Exception as e:
            await browser.close()
            return f"Error: {str(e)[:50]}"


async def test_tor_connection():
    """TOR ishlashini test qilish"""
    print("\n🧅 TOR CONNECTION TEST")
    print("-" * 60)

    # 1. TOR yoqilganini tekshirish
    try:
        tor_ip = await get_current_ip(TOR_PROXY)
        print(f"✅ TOR ishlayapti! IP: {tor_ip}")

        # 2. TOR circuit'ini restart qilish (yangi IP olish)
        print("🔄 Yangi TOR circuit olish...")
        # Bu yerda TOR controller orqali yangi circuit so'rash mumkin
        # Lekin sodda usul: biroz kutish, TOR o'zi yangilaydi
        await asyncio.sleep(2)

        new_tor_ip = await get_current_ip(TOR_PROXY)
        print(f"🆕 Yangi IP: {new_tor_ip}")

        return True
    except Exception as e:
        print(f"❌ TOR ishlamayapti: {e}")
        return False


async def scrape_with_advanced_bypass(target_url, api_url, method="direct"):
    """
    Kengaytirilgan bypass usullari
    method: direct, tor, tor_slow, proxy, vpn
    """
    async with async_playwright() as p:
        launch_options = {
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
            ]
        }

        # Proxy tanlash
        proxy_config = None
        timeout_ms = 60000

        if method == "tor":
            proxy_config = TOR_PROXY
            timeout_ms = 120000  # TOR uchun ko'proq vaqt
            print("🧅 TOR orqali (standart)")
        elif method == "tor_slow":
            proxy_config = TOR_PROXY
            timeout_ms = 180000  # 3 minut - juda sekin saytlar uchun
            print("🐌 TOR orqali (sekin rejim - 3 min timeout)")
        elif method == "proxy" and FREE_PROXIES:
            proxy_config = random.choice(FREE_PROXIES)
            print(f"🌐 Proxy orqali: {proxy_config['server']}")
        elif method == "vpn" and VPN_PROXY.get('server'):
            proxy_config = VPN_PROXY
            print(f"🔐 VPN orqali: {proxy_config['server']}")
        else:
            print("🔓 To'g'ridan-to'g'ri (proxy/VPN yo'q)")

        if proxy_config:
            launch_options['proxy'] = proxy_config

        browser = await p.chromium.launch(**launch_options)

        # Stealth context
        selected_user_agent = random.choice(USER_AGENTS)
        context = await browser.new_context(
            user_agent=selected_user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Asia/Tashkent',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9,uz;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Connection': 'keep-alive',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1',
            }
        )

        page = await context.new_page()

        # Anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        print(f"🎭 User-Agent: {selected_user_agent[:50]}...")

        try:
            # IP tekshirish
            if proxy_config:
                try:
                    ip_page = await context.new_page()
                    await ip_page.goto('https://api.ipify.org?format=json', timeout=15000)
                    ip_data = await ip_page.evaluate('() => document.body.innerText')
                    print(f"🌍 Hozirgi IP: {ip_data}")
                    await ip_page.close()
                except:
                    print("⚠️ IP tekshirib bo'lmadi (normal, davom etamiz)")

            # Saytga kirish (katta timeout bilan)
            print(f"📡 Ulanish: {target_url} (timeout: {timeout_ms / 1000}s)")
            start_time = time.time()

            await page.goto(
                target_url,
                timeout=timeout_ms,
                wait_until='domcontentloaded'  # networkidle emas, tezroq
            )

            load_time = time.time() - start_time
            print(f"⏱️ Sahifa yuklandi: {load_time:.2f}s")

            # Random delay
            await asyncio.sleep(random.uniform(2, 4))

            # API so'rovi
            print(f"📥 API: {api_url}")
            data = await page.evaluate(f"""
                async () => {{
                    try {{
                        const res = await fetch('{api_url}');
                        if (!res.ok) throw new Error('HTTP ' + res.status);
                        return await res.json();
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
            """)

            if data and 'error' not in data:
                print("✅ Ma'lumot olindi!")
                # Faqat qisqa natija ko'rsatish
                if isinstance(data, dict):
                    keys = list(data.keys())[:3]
                    print(f"📊 Data keys: {keys}...")
                return data
            else:
                print(f"⚠️ API xatolik: {data.get('error', 'Unknown')}")
                return None

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Xatolik: {error_msg[:100]}")

            # Screenshot
            try:
                screenshot_name = f'error_{method}_{int(time.time())}.png'
                await page.screenshot(path=screenshot_name, timeout=5000)
                print(f"📸 Screenshot: {screenshot_name}")
            except:
                pass

            return None

        finally:
            await context.close()
            await browser.close()


async def rotate_tor_identity():
    """
    TOR identity'sini o'zgartirish (yangi circuit)
    Bu uchun TOR Controller kerak
    """
    try:
        from stem import Signal
        from stem.control import Controller

        with Controller.from_port(port=9051) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
            print("✅ TOR identity yangilandi!")
            await asyncio.sleep(5)  # Yangi circuit tayyor bo'lguncha
            return True
    except ImportError:
        print("⚠️ 'stem' kutubxonasi o'rnatilmagan: pip install stem")
        return False
    except Exception as e:
        print(f"⚠️ TOR identity yangilab bo'lmadi: {e}")
        return False


async def main():
    """
    Barcha usullarni ketma-ket sinash
    """
    print("=" * 70)
    print("🚀 ADVANCED IP BYPASS TEST - REAL WORLD SCENARIO")
    print("=" * 70)

    # O'Z SAYT URL'LARINGIZNI BU YERGA KIRITING!
    TARGET_URL = "https://ish.mehnat.uz/vacancies"
    API_URL = "https://api.mehnat.uz/api/v1/vacancies?per_page=5&isVisible=true&page=1"

    print(f"\n🎯 Target: {TARGET_URL}")
    print(f"🎯 API: {API_URL}")

    # Hozirgi IP
    current_ip = await get_current_ip()
    print(f"\n📍 Server IP (bloklangan): {current_ip}")
    print("=" * 70)

    results = {}

    # TEST 1: To'g'ridan-to'g'ri (bloklangan)
    print("\n1️⃣ TO'G'RIDAN-TO'G'RI (bloklangan IP)")
    print("-" * 70)
    results['direct'] = await scrape_with_advanced_bypass(TARGET_URL, API_URL, "direct")
    await asyncio.sleep(3)

    # TEST 2: TOR (standart timeout)
    print("\n\n2️⃣ TOR ORQALI (standart - 2min timeout)")
    print("-" * 70)
    results['tor'] = await scrape_with_advanced_bypass(TARGET_URL, API_URL, "tor")
    await asyncio.sleep(3)

    # TEST 3: TOR (sekin rejim)
    print("\n\n3️⃣ TOR ORQALI (sekin rejim - 3min timeout)")
    print("-" * 70)
    results['tor_slow'] = await scrape_with_advanced_bypass(TARGET_URL, API_URL, "tor_slow")

    # NATIJALAR
    print("\n\n" + "=" * 70)
    print("📊 FINAL NATIJALAR:")
    print("=" * 70)
    for method, result in results.items():
        status = "✅ MUVAFFAQIYATLI" if result else "❌ MUVAFFAQIYATSIZ"
        print(f"{method.upper():20} : {status}")
    print("=" * 70)

    # Tavsiyalar
    print("\n💡 TAVSIYALAR:")
    if not results.get('tor') and not results.get('tor_slow'):
        print("""
1. TOR exit node'lar bloklangan bo'lishi mumkin
2. Bepul proxy sinab ko'ring (FREE_PROXIES ga qo'shing)
3. VPN ishlatib ko'ring (tezroq va ishonchli)
4. Cloud server'dan ishlatib ko'ring (AWS, DigitalOcean)
5. Residential proxy xizmatlari (pullik lekin ishonchli):
   - Bright Data (luminati.io)
   - Oxylabs
   - Smartproxy
        """)


async def test_multiple_proxies():
    """
    Bir nechta proxy'ni ketma-ket sinash
    """
    print("\n🔄 KO'P PROXY SINOVI")
    print("=" * 70)

    test_proxies = [
        TOR_PROXY,
        # Bu yerga bepul proxy'lar qo'shing
    ]

    for i, proxy in enumerate(test_proxies, 1):
        print(f"\n{i}. Proxy: {proxy['server']}")
        ip = await get_current_ip(proxy)
        print(f"   IP: {ip}")
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())

    # Qo'shimcha testlar (kerak bo'lsa uncomment qiling)
    # asyncio.run(test_tor_connection())
    # asyncio.run(test_multiple_proxies())