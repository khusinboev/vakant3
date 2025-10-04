import asyncio
import json
import random
import time
from playwright.async_api import async_playwright

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
]

# O'ZBEKISTON PROXY'LAR - bu yerga https://spys.one/free-proxy-list/UZ/ dan oling
UZ_PROXIES = [
    'http://195.158.10.99:8080',
    'http://91.213.99.134:3128',
    'http://89.104.102.209:58080',
    # Ko'proq qo'shing...
]

TARGET_URL = "https://ish.mehnat.uz/vacancies"
API_URL = "https://api.mehnat.uz/api/v1/vacancies?per_page=5&isVisible=true&page=1"


async def test_single_proxy(proxy_url):
    """Bitta proxy'ni test qilish"""
    print(f"\n{'=' * 70}")
    print(f"Testing: {proxy_url}")
    print('=' * 70)

    start = time.time()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                proxy={'server': proxy_url}
            )

            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale='uz-UZ',
                timezone_id='Asia/Tashkent',
            )

            page = await context.new_page()

            # IP tekshirish
            print("Checking IP...")
            try:
                await page.goto('https://api.ipify.org?format=json', timeout=10000)
                ip = await page.evaluate('() => document.body.innerText')
                print(f"IP: {ip}")
            except:
                print("IP check failed")

            # Asosiy test
            print(f"Connecting to: {TARGET_URL}")
            await page.goto(TARGET_URL, timeout=45000, wait_until='domcontentloaded')
            print(f"Page loaded! ({time.time() - start:.1f}s)")

            await asyncio.sleep(2)

            # API
            print(f"Fetching API: {API_URL}")
            data = await page.evaluate(f"""
                async () => {{
                    try {{
                        const res = await fetch('{API_URL}');
                        return await res.json();
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
            """)

            await browser.close()

            if data and 'error' not in data:
                elapsed = time.time() - start
                print(f"\nSUCCESS! Data received in {elapsed:.1f}s")
                print(f"Sample: {str(data)[:150]}...")
                return True
            else:
                print(f"\nAPI Error: {data.get('error', 'Unknown')}")
                return False

        except Exception as e:
            print(f"\nFAILED: {str(e)[:100]}")
            try:
                await browser.close()
            except:
                pass
            return False


async def main():
    print("=" * 70)
    print("O'ZBEKISTON PROXY TEST - SIMPLE VERSION")
    print("=" * 70)
    print(f"\nTarget: {TARGET_URL}")
    print(f"API: {API_URL}\n")

    # 1. Direct (bloklangan)
    print("\n1. DIRECT CONNECTION (Blocked IP)")
    print("-" * 70)
    result = await test_single_proxy(None)

    # 2. Har bir proxy
    success = False
    for i, proxy in enumerate(UZ_PROXIES, 2):
        print(f"\n{i}. UZ PROXY #{i - 1}")
        print("-" * 70)
        result = await test_single_proxy(proxy)
        if result:
            success = True
            print("\n" + "=" * 70)
            print("BYPASS SUCCESSFUL!")
            print("=" * 70)
            break
        await asyncio.sleep(2)

    if not success:
        print("\n" + "=" * 70)
        print("ALL PROXIES FAILED")
        print("Try adding fresh proxies from:")
        print("  - https://spys.one/free-proxy-list/UZ/")
        print("  - https://free-proxy-list.net/")
        print("=" * 70)


async def quick_proxy_test():
    """Faqat proxy'larni tezkor test qilish"""
    print("QUICK PROXY TEST")
    print("=" * 70)

    for i, proxy in enumerate(UZ_PROXIES, 1):
        print(f"\n{i}. Testing: {proxy}")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy={'server': proxy}
                )
                page = await browser.new_page()
                await page.goto('https://api.ipify.org?format=json', timeout=8000)
                ip = await page.evaluate('() => document.body.innerText')
                await browser.close()
                print(f"   WORKS! IP: {ip}")
        except Exception as e:
            print(f"   FAILED: {str(e)[:60]}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        asyncio.run(quick_proxy_test())
    else:
        asyncio.run(main())