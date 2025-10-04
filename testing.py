import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://ish.mehnat.uz/vacancies", timeout=60000)

        # Sayt yuklangandan keyin JS orqali fetch bilan olish
        data = await page.evaluate("""
        async () => {
            const res = await fetch('https://ishapi.mehnat.uz/api/v1/vacancies?per_page=5&isVisible=true&page=1');
            return await res.json();
        }
        """)

        print(json.dumps(data, indent=2, ensure_ascii=False))
        await browser.close()

asyncio.run(main())
