# save as fetch_aiohttp.py
import aiohttp
import asyncio
import json

API_URL = "https://ishapi.mehnat.uz/api/v1/vacancies"

DEFAULT_PARAMS = {
    "per_page": 5,
    "kodp_keys": "[]",
    "vacancy_soato_code": 1733,
    "pagination_type": "simplePaginate",
    "sort_key": "created_at",
    "nskz": "213,312",
    "is_reserved": 0,
    "for_students": 0,
    "isVisible": "true",
    "page": 1
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://ish.mehnat.uz/"
}

async def fetch_page(session, params):
    try:
        async with session.get(API_URL, params=params) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}: {text[:400]}")
            return await resp.json()
    except Exception as e:
        raise

async def main(fetch_all_pages: bool = False):
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
        params = DEFAULT_PARAMS.copy()
        page = params["page"]
        total_items = 0
        first_item = None

        while True:
            params["page"] = page
            data = await fetch_page(session, params)
            # safety checks
            if not data.get("success") or "data" not in data:
                print("Unexpected response structure:", data)
                return

            page_block = data["data"]
            items = page_block.get("data") or []
            if page == 1 and items:
                first_item = items[0]

            total_items += len(items)

            # if not fetching all pages, break after first
            if not fetch_all_pages:
                break

            # pagination detection: try next_page_url or check if len(items) < per_page
            next_url = page_block.get("next_page_url")
            if not next_url or len(items) == 0:
                break
            page += 1

        print("Jami (yig'ilgan) ishlar soni (o'qingan sahifalar bo'yicha):", total_items)
        if first_item:
            print("\nBirinchi ish (raw JSON):")
            print(json.dumps(first_item, ensure_ascii=False, indent=2))
        else:
            print("Hech narsa topilmadi.")

if __name__ == "__main__":
    # agar barcha sahifalarni yig'ishni xohlasangiz: main(fetch_all_pages=True)
    asyncio.run(main(fetch_all_pages=True))
