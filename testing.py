import asyncio
import json
import random
from playwright.async_api import async_playwright

# 1. USER AGENT ROTATION (Header Forgery)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

# 2. PROXY ROTATION (misol - siz o'z proxy'laringizni qo'shasiz)
PROXIES = [
    # Misol format:
    # {'server': 'http://proxy1.com:8080', 'username': 'user', 'password': 'pass'},
    # {'server': 'http://proxy2.com:8080'},
]

# 3. TOR PROXY KONFIGURATSIYASI
TOR_PROXY = {
    'server': 'socks5://127.0.0.1:9050'  # Tor default port
}


async def scrape_with_stealth(use_tor=False, use_proxy=False):
    """
    Barcha stealth texnikalarni qo'llagan holda scraping
    """
    async with async_playwright() as p:
        # Browser launch options
        launch_options = {
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',  # Automation detection o'chirish
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        }

        # Agar TOR ishlatmoqchi bo'lsak
        if use_tor:
            launch_options['proxy'] = TOR_PROXY
            print("🧅 TOR orqali ulanish...")
        # Yoki oddiy proxy
        elif use_proxy and PROXIES:
            launch_options['proxy'] = random.choice(PROXIES)
            print(f"🌐 Proxy orqali ulanish: {launch_options['proxy']['server']}")

        browser = await p.chromium.launch(**launch_options)

        # User-Agent ni tanlash
        selected_user_agent = random.choice(USER_AGENTS)

        # Context yaratish (fingerprint spoofing uchun)
        context = await browser.new_context(
            user_agent=selected_user_agent,  # Random User-Agent
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Asia/Tashkent',
            # Extra headers
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )

        # User-Agent ni saqlash (print uchun)
        selected_user_agent = random.choice(USER_AGENTS)

        page = await context.new_page()

        # 4. BROWSER FINGERPRINT SPOOFING
        # WebDriver detection ni yashirish
        await page.add_init_script("""
            // Navigator.webdriver ni o'chirish
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Chrome object qo'shish (agar Firefox User-Agent bo'lmasa)
            window.chrome = {
                runtime: {}
            };

            // Permissions API ni override qilish
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Plugin va mimeTypes qo'shish
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)

        print(f"🎭 Fingerprint spoofing aktiv")
        print(f"🔧 User-Agent: {selected_user_agent[:60]}...")

        try:
            # Saytga kirish
            print(f"📡 Saytga ulanish: https://ish.mehnat.uz/vacancies")
            await page.goto("https://ish.mehnat.uz/vacancies",
                            timeout=60000,
                            wait_until='networkidle')

            # Random delay (bot detection oldini olish)
            await asyncio.sleep(random.uniform(1, 3))

            # API orqali ma'lumot olish
            print("📥 API dan ma'lumot olish...")
            data = await page.evaluate("""
                async () => {
                    try {
                        const res = await fetch('https://ishapi.mehnat.uz/api/v1/vacancies?per_page=5&isVisible=true&page=1');
                        return await res.json();
                    } catch (e) {
                        return { error: e.message };
                    }
                }
            """)

            # IP manzilni tekshirish (agar TOR/Proxy ishlatilsa)
            if use_tor or use_proxy:
                try:
                    ip_page = await context.new_page()
                    await ip_page.goto('https://api.ipify.org?format=json', timeout=10000)
                    ip_data = await ip_page.evaluate('() => document.body.innerText')
                    print(f"🌍 Sizning IP: {ip_data}")
                    await ip_page.close()
                except:
                    print("⚠️ IP tekshirib bo'lmadi")

            print("\n✅ Muvaffaqiyatli! Natija:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            return data

        except Exception as e:
            print(f"❌ Xatolik: {e}")
            # Screenshot olish (debug uchun)
            await page.screenshot(path='error_screenshot.png')
            print("📸 Screenshot saqlandi: error_screenshot.png")
            return None

        finally:
            await context.close()
            await browser.close()


async def main():
    """
    Turli usullarni sinab ko'rish
    """
    print("=" * 60)
    print("🚀 ADVANCED WEB SCRAPING TEST")
    print("=" * 60)

    # 1. Oddiy usul
    print("\n1️⃣ ODDIY USUL (Hech qanday stealth yoq)")
    print("-" * 60)
    await scrape_with_stealth(use_tor=False, use_proxy=False)

    await asyncio.sleep(3)

    # 2. Stealth usul (fingerprint spoofing + headers)
    print("\n\n2️⃣ STEALTH USUL (Fingerprint spoofing + Header forgery)")
    print("-" * 60)
    await scrape_with_stealth(use_tor=False, use_proxy=False)

    # 3. TOR orqali (agar Tor o'rnatilgan bo'lsa)
    # print("\n\n3️⃣ TOR ORQALI")
    # print("-" * 60)
    # await scrape_with_stealth(use_tor=True, use_proxy=False)

    print("\n\n" + "=" * 60)
    print("✅ Barcha testlar tugadi!")
    print("=" * 60)


# TOR ishlatish uchun qo'shimcha funksiya
async def test_with_tor():
    """
    TOR orqali test qilish
    Avval TOR o'rnatilgan bo'lishi kerak:
    - Ubuntu/Debian: sudo apt install tor && sudo service tor start
    - Mac: brew install tor && brew services start tor
    - Windows: Tor Browser ishga tushiring yoki Tor standalone o'rnating
    """
    print("🧅 TOR TEST")
    print("Tor ishga tushirilganligiga ishonch hosil qiling!")
    print("Default: socks5://127.0.0.1:9050")
    print("-" * 60)
    await scrape_with_stealth(use_tor=True, use_proxy=False)


if __name__ == "__main__":
    # Oddiy test
    asyncio.run(main())

    # TOR test (agar kerak bo'lsa uncomment qiling)
    # asyncio.run(test_with_tor())