import aiohttp
import asyncio
import sqlite3
# from config import db, sql

# reg0 = sql.execute(f"""SELECT region FROM users WHERE user_id = {5484714936}""").fetchone()[0]
#
#
# reg1 = sql.execute(f"""SELECT reg_ids FROM locations WHERE regions = {5484714936}""").fetchone()[0]
BASE_DIR = str(Path(__file__).resolve().parent)+"/src/database/"
db = sqlite3.connect(BASE_DIR+'database.sqlite3')
sql = db.cursor()
sql.execute("DELETE FROM users")  # Barcha ma'lumotlarni o‘chirish
db.commit()


print("Barcha ma'lumotlar o‘chirildi!")











# sql.execute("""
# CREATE TABLE IF NOT EXISTS viloyatlar (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     my_num INTEGER NOT NULL,
#     nom TEXT UNIQUE NOT NULL
# )
# """)
#
# # Tumanlar jadvalini yaratish
# sql.execute("""
# CREATE TABLE IF NOT EXISTS tumanlar (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     vil_num INTEGER NOT NULL,
#     my_num INTEGER NOT NULL,
#     nom TEXT NOT NULL,
#     FOREIGN KEY (vil_num) REFERENCES viloyatlar (vil_num)
# )
# """)
# # https://ishapi.mehnat.uz/api/v1/vacancies?per_page=5&salary=2000000&kodp_keys=null&vacancy_soato_code=1706204&sort_key=salary_asc&nskz=22,322,323,324&page=1
#
# async def get_site_content(URL):
#     # connector = ProxyConnector.from_url('http://213.230.127.137:3128')
#     async with aiohttp.ClientSession() as session:
#         async with session.get(URL, ssl=False) as resp:
#             text = await resp.json()
#     return text
#
# soup = asyncio.run(get_site_content("https://ishapi.mehnat.uz/api/v1/resources/regions"))
# if soup["success"]:
#     for i in range(0, len(soup["data"])):
#         region_name = soup["data"][i]['name_uz_ln']
#         region_id = soup["data"][i]['soato']
#         soup2 = asyncio.run(get_site_content(f"https://ishapi.mehnat.uz/api/v1/resources/districts?region_soato={region_id}"))
#         sql.execute("INSERT OR IGNORE INTO viloyatlar (my_num, nom) VALUES (?, ?)", (region_id, region_name))
#         db.commit()
#         for j in range(0, len(soup2['data'])):
#             district_id = soup2['data'][j]['soato']
#             district_name = soup2['data'][j]['name_uz_ln']
#
#             sql.execute("INSERT OR IGNORE INTO tumanlar (vil_num, my_num, nom) VALUES (?, ?, ?)", (region_id, district_id, district_name))
#         db.commit()
# db.close()
