# save as fetch_playwright.py
import asyncio
import json
from playwright.async_api import async_playwright

API_URL = "https://ishapi.mehnat.uz/api/v1/vacancies"
DEFAULT_PARAMS = {
    "per_page": "5",
    "kodp_keys": "[]",
    "vacancy_soato_code": "1733",
    "pagination_type": "simplePaginate",
    "sort_key": "created_at",
    "nskz": "213,312",
    "is_reserved": "0",
    "for_students": "0",
    "isVisible": "true",
    "page": "1"
}

async def main(fetch_all_pages: bool = False):
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)  # yoki chromium
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        # Biz request context orqali to'g'ridan-to'g'ri APIga so'rov yuboramiz:
        request = context.request

        page_num = 1
        total_items = 0
        first_item = None

        while True:
            params = DEFAULT_PARAMS.copy()
            params["page"] = str(page_num)
            # build query string
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = API_URL + "?" + query
            resp = await request.get(url, headers={"Referer": "https://ish.mehnat.uz/"})
            if resp.status != 200:
                text = await resp.text()
                print("HTTP error:", resp.status, text[:400])
                break
            data = await resp.json()
            page_block = data.get("data") or {}
            items = page_block.get("data") or []
            if page_num == 1 and items:
                first_item = items[0]
            total_items += len(items)

            if not fetch_all_pages:
                break

            next_url = page_block.get("next_page_url")
            if not next_url or len(items) == 0:
                break
            page_num += 1

        print("Jami ishlar soni (o'qingan sahifalar bo'yicha):", total_items)
        if first_item:
            print("\nBirinchi ish (raw JSON):")
            print(json.dumps(first_item, ensure_ascii=False, indent=2))
        else:
            print("Hech narsa topilmadi.")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    # fetch_all_pages=True nusxalar yig'ish uchun (ehtiyotkorlik bilan)
    asyncio.run(main(fetch_all_pages=True))
