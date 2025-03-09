from sqlite3 import connect

# from aiohttp_proxy import ProxyConnector

from aiogram import *
from aiogram.types import *
import asyncio
import aiohttp

from config import sql, db, dp


###   Admin panel uchun kerakli funksiyalar
class functions:
    @staticmethod
    async def check_on_start(user_id):
        rows = sql.execute("SELECT id FROM channels").fetchall()
        error_code = 0
        for row in rows:
            r = await dp.bot.get_chat_member(chat_id=row[0], user_id=user_id)
            if r.status in ['member', 'creator', 'admin']:
                pass
            else:
                error_code = 1
        if error_code == 0:
            return True
        else:
            return False

class panel_func:
    @staticmethod
    async def channel_add(id):
        sql.execute("""CREATE TABLE IF NOT EXISTS channels(id)""")
        db.commit()
        sql.execute("INSERT INTO channels VALUES(?);", id)
        db.commit()


    @staticmethod
    async def channel_delete(id):
        sql.execute(f'DELETE FROM channels WHERE id = "{id}"')
        db.commit()

    @staticmethod
    async def channel_list():
        sql.execute("SELECT id from channels")
        str = ''
        for row in sql.fetchall():
            id = row[0]
            try:
                all_details = await dp.bot.get_chat(chat_id=id)
                title = all_details["title"]
                channel_id = all_details["id"]
                info = all_details["description"]
                str+= f"------------------------------------------------\nKanal useri: > {id}\nKamal nomi: > {title}\nKanal id si: > {channel_id}\nKanal haqida: > {info}\n"
            except:
                str+= "Kanalni admin qiling"
        return str

async def forward_send_msg(chat_id: int, from_chat_id: int, message_id: int) -> int:
    try:
        await dp.bot.forward_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
        return 1
    except:
        return 0

async def send_message_chats(chat_id: int, from_chat_id: int, message_id: int) -> int:
    try:
        await dp.bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
        return 1
    except:
        return 0


### kanalga qo'shilish
async def join_inline_btn(user_id):
    sql.execute("SELECT id FROM channels")
    rows = sql.fetchall()
    join_inline = types.InlineKeyboardMarkup(row_width=1)
    title = 1
    for row in rows:
        all_details = await dp.bot.get_chat(chat_id=row[0])
        url = all_details['invite_link']
        join_inline.insert(InlineKeyboardButton(f"{title} - kanal", url=url))
        title += 1
    join_inline.add(InlineKeyboardButton("✅Obuna bo'ldim", callback_data="check"))

    return join_inline


##    Parsing uchun funksiya

async def get_site_content(URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(URL, ssl=False) as resp:
            text = await resp.json()
    return text


async def search_vakant(user_id, bet):
        reg0 = sql.execute(f"""SELECT region FROM users WHERE user_id = {user_id}""").fetchone()[0]
        reg1 = sql.execute(f"""SELECT district FROM users WHERE user_id = {user_id} """).fetchone()[0]
        specs = sql.execute(f"""SELECT specs FROM users WHERE user_id = {user_id} """).fetchone()[0]
        if specs==None:
            soha = ""
        else:
            soha = specs
        if reg0 is None:
            yurt = ''
        else:
            if reg1 is None:
                yurt = sql.execute(f"""SELECT reg_ids FROM locations WHERE regions = "{reg0}" """).fetchone()[0]
            else:
                print(reg1)
                yurt = sql.execute(f"""SELECT dist_ids FROM locations WHERE districts = "{reg1}" """).fetchone()[0]

        oyliq_basa = sql.execute(f"""SELECT money FROM users WHERE user_id = {user_id}""").fetchone()[0]
        if oyliq_basa == None:
            oyliq=''
        else:
            oyliq=oyliq_basa

        url2 = f'https://ishapi.mehnat.uz/api/v1/vacancies?per_page=5&salary={oyliq}&vacancy_soato_code={yurt}&sort_key=salary_asc&nskz={soha}&page={bet}'
        soup = await get_site_content(url2)

        try:
            text = soup['data']['data']

            num = soup['data']['from']
            texts = ''
            ids = []
            for i in text:

                id = i['id']
                company_name = i['company_name']
                position_name = i['position_name']
                position_salary = i['position_salary']
                if position_salary == None:
                    position_salary = "Mavjud emas"
                date_start = i['date_start']
                texts += f"""<b>👨‍💻{num}- VAKANSIYA\n\n🆔ID raqami: </b>{id}\n<b>🏬 Ish beruvchi: </b>{company_name}\n<b>💺 Lavozim</b>: {position_name}\n<b>💰Maoshi: </b>{position_salary} so'm\n<b>⏰ Ish joylangan sana: </b>{date_start}\n------------------------------------\n"""
                num += 1
                ids.append(id)
            all = soup['data']['total']
            dan = soup['data']['from']
            ga = soup['data']['to']
            joriy = soup['data']['current_page']
            end = soup['data']['last_page']
            texts = f"<b>NATIJALAR</b>: {all} ta bo'sh ish o'rinlari topildi | {dan}-{ga}\n" + texts
            if dan == None:
                texts = "Sizning belgilagan filterlaringiz bo'yicha ma'lumot topilmadi, Filtrlarni o'zgartirib ko'ring"
        except:
            texts="Xato yuz berdi"
            ids = 1
            joriy = 0
            dan = 0
            end = 0
        return texts, ids, joriy, dan, end


async def vacancie_btn(ids, joriy, ga):
    region_choos = types.InlineKeyboardMarkup(row_width=5)
    for name, id in zip(range(ga, ga+10), ids):
        region_choos.insert(InlineKeyboardButton(name, callback_data=id))

    region_choos.add(InlineKeyboardButton("⬅", callback_data=f"⬅{joriy}"))
    region_choos.insert(InlineKeyboardButton("❌", callback_data="❌"))
    region_choos.insert(InlineKeyboardButton("➡", callback_data=f"➡{joriy}"))
    return region_choos


###  Viloyat va tumanlarni basadan olish

async def get_regions():
    sql.execute("SELECT my_num, nom FROM viloyatlar")
    # nom = [i[0] for i in sql.fetchall()]
    # my_num = [i[1] for i in sql.fetchall()]
    all = [i for i in sql.fetchall()]
    return all


########################         tugmalarni chiqarish uchun funksiyalar

async def region_btn(user_id):
    regs = ['Barchasi'] + [r1 for r, r1 in await get_regions()]
    region_choos = types.InlineKeyboardMarkup(row_width=2)
    title = 1
    for row in regs:
        reg = sql.execute(f"""SELECT region FROM users WHERE user_id = {user_id}""").fetchone()

        if row == reg[0]:
            region_choos.insert(InlineKeyboardButton(text=f"🟢{row}", callback_data=row))
        else:
            if reg[0] is None and row == 'Barchasi':
                region_choos.insert(InlineKeyboardButton(text=f"🟢{row}", callback_data=row))
            else:
                region_choos.insert(InlineKeyboardButton(row, callback_data=row))
        title += 1
    return region_choos


async def district_btn(user_id):
    regs = sql.execute(f"""SELECT region FROM users WHERE user_id = {user_id}""").fetchone()[0]
    districts = ['Barchasi.'] + [dis[0] for dis in sql.execute(f"""SELECT districts FROM locations WHERE regions = "{regs}" """).fetchall()]

    region_choos = types.InlineKeyboardMarkup(row_width=2)
    title = 1
    for row in districts:
        reg = sql.execute(f"""SELECT district FROM users WHERE user_id = {user_id}""").fetchone()
        if row == reg[0]:
            region_choos.insert(InlineKeyboardButton(text=f"🟢{row}", callback_data=row))
        else:
            if reg[0] is None and row == 'Barchasi.':
                region_choos.insert(InlineKeyboardButton(text=f"🟢{row}", callback_data=str(row[1])))
            else:
                region_choos.insert(InlineKeyboardButton(row, callback_data=row))
        title += 1
    return region_choos


async def money_btn(user_id):
    rr = [('⭕️Ahamiyatsiz️',0), ('2 mln ➕',2000000), ('3 mln ➕',3000000), ('4 mln ➕',4000000), ('5 mln ➕',5000000)]
    # rows = ['⭕️Ahamiyatsiz️', '2 mln ➕', '3 mln ➕', '4 mln ➕', '5 mln ➕']
    region_choos = types.InlineKeyboardMarkup(row_width=2)
    title = 1
    for row in rr:
        reg = sql.execute(f"""SELECT money FROM users WHERE user_id = {user_id}""").fetchone()

        if row == reg[0]:
            region_choos.insert(InlineKeyboardButton(text=f"🟢{row[0]}", callback_data=str(row[1])))
        else:
            if reg[0] is None and row == '⭕️Ahamiyatsiz️':
                region_choos.insert(InlineKeyboardButton(text=f"🟢{row}", callback_data=str(row[1])))
            else:
                region_choos.insert(InlineKeyboardButton(row[0], callback_data=str(row[1])))
        title += 1
    return region_choos


async def special_btn(user_id):
    specs = ["Sog'liqni saqlash", "Qurilish sohasi", "Savdo va xizmat ko'rsatish", "Qishloq xo'jaligi", "Arxitektura va Texnika", "IT sohasi", "Ta'lim sohasi", "Haydovchilik sohasi"]
    backs = ['22,322,323,324', '71', '91,522,523', '61', '214', '213,312', '23,33', '83']

    spec_choos = types.InlineKeyboardMarkup(row_width=2)
    for spec, back in zip(specs, backs):
        reg = sql.execute(f"""SELECT specs FROM users WHERE user_id = {user_id}""").fetchone()[0]
        sp = str(reg)
        if back == sp:
            spec_choos.insert(InlineKeyboardButton(text=f"🟢{spec}", callback_data=back))
        else:
            spec_choos.insert(InlineKeyboardButton(spec, callback_data=back))
    return spec_choos


#######################

async def saves_info(data):
    url = f'https://ishapi.mehnat.uz/api/v1/vacancies/{data}'
    soup = await get_site_content(url)
    if soup["success"]:
        soup1 = soup['data']
        status = soup1["active"]
        if status == True:
            status = "Aktiv"
        else:
            status = "Band"
        comp_name = soup1['company_name']
        work_title = soup1['position_name']
        salary = soup1['position_salary']
        commitment = soup1['position_duties']
        demand = soup1['position_requirements']
        condition = soup1['position_conditions']
        phones = soup1['phones']
        address = str(soup1['region']['name_uz_ln']) + ', ' + str(soup1['district']['name_uz_ln'])
        text = f"<b>🏢Komponiya nomi: </b>{comp_name}\n<b>🧑‍🏭Ish nomi: </b>{work_title}\n\n<b>ℹ️Ish haqida: </b>{condition}\n\n<b>📌Majburiyatlari: </b>{commitment}\n\n<b>📎Talab: </b>{demand}\n\n<b>💸Maoshi: </b>{salary}\n\n\n<b>📣Ishning holati: </b>{status}\n<b>🗺Manzili: </b>{address}\n<b>📞Telefon raqami: </b>+{phones[0]}"
    else:
        text = "Not Found"
    return text
