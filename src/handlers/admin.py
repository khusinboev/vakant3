from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.utils.exceptions import *
from src.buttons.buttuns import *
from src.functions.functions import *

class From(StatesGroup):
	channelAdd = State()
	channelDelete = State()
	send_msg = State()
	forward_msg = State()
	clear_msg = State()

	sent_num = State()

	one_S = State()


@dp.message_handler(commands = ["developer", 'coder', 'programmer'])
async def coder(msg: types.Message):
	await msg.reply("Bot dasturchisi @coder_admin_py\n\nPowered by @coder_admin_py", parse_mode='html')

Admin = [5246872049, 619839487, 1918760732]
markup = ReplyKeyboardMarkup(resize_keyboard=True)
markup.add("🔙Orqaga qaytish")
@dp.message_handler(commands=['admin', 'panel'], user_id = Admin)
async def new(msg: types.Message):
	await msg.answer("Assalomu alaykum admin janoblari", reply_markup=main_btn)
	# await From.teststate.set()   state=From.teststate,

@dp.message_handler(text = "🔙Orqaga qaytish", user_id = Admin)
async def backs(message: types.Message):
	await message.reply("Bosh menyu", reply_markup=main_btn)

############################          STATISTIKA            """"""""""""""""""""""

@dp.message_handler( text = "📊Statistika", user_id = Admin)
async def new(msg: types.Message):
	sql.execute("SELECT COUNT(*) FROM users WHERE lang = ?", ('uz',))
	followersuz = sql.fetchone()[0]
	sql.execute("SELECT COUNT(*) FROM users WHERE lang = ?", ('ru',))
	followersru = sql.fetchone()[0]
	sql.execute("SELECT COUNT(*) FROM users WHERE lang = ?", ('en',))
	followersen = sql.fetchone()[0]
	sql.execute("SELECT COUNT(*) FROM users")
	followersall = sql.fetchone()[0]
	await msg.answer(f"👥Botdagi jami azolar soni👇👇\n\n🇺🇿O'zbeklar soni {followersuz}\n\n🇷🇺Ruslar soni - {followersru}\n\n🇺🇸Ingilizlar soni - {followersen}\n\n👤Jami azolar soni: > {followersall}")

###########################           KANALLAR              """""""""""""""""""""

@dp.message_handler(text = '🔧Kanallar', user_id = Admin)
async def new(msg: types.Message):
	await msg.answer("Tanlang", reply_markup=channel_btn)


@dp.message_handler(text = "➕Kanal qo'shish", user_id = Admin)
async def channel_add(message: types.Message):
	markup = ReplyKeyboardMarkup(resize_keyboard=True)
	markup.add("🔙Orqaga qaytish")
	await message.reply("Kanal qo'shish uchun kanalning userini yuboring.\nMisol uchun @coder_admin", reply_markup=markup)
	await From.channelAdd.set()


@dp.message_handler(state=From.channelAdd, user_id = Admin)
async def channelAdd1(message: types.Message, state: FSMContext):
	channel_id = [message.text.upper()]
	data = sql.execute(f"SELECT id FROM channels WHERE id = '{message.text.upper()}'").fetchone()
	if data is None:
		if message.text[0]=='@':
			await panel_func.channel_add(channel_id)
			await state.finish()
			await message.reply("Kanal qo'shildi🎉🎉", reply_markup=channel_btn)
		else:
			await message.reply("Kanal useri xato kiritildi\nIltimos userni @coder_admin ko'rinishida kiriting", reply_markup=channel_btn)
	else:
		await message.reply("Bu kanal avvaldan bor", reply_markup=channel_btn)
	await state.finish()


@dp.message_handler(text = "❌Kanalni olib tashlash", user_id = Admin)
async def channelD(message: types.Message):
	await message.reply("O'chiriladigan kanalning userini yuboring.\nMisol uchun @coder_admin", reply_markup=markup)
	await From.channelDelete.set()

@dp.message_handler(state=From.channelDelete, user_id = Admin)
async def ChannelDel(message: types.Message, state: FSMContext):
	channel_id = message.text.upper()
	data = sql.execute(f"""SELECT id FROM channels WHERE id = '{channel_id}'""").fetchone()
	if data is None:
		await message.reply("Bunday kanal yo'q", reply_markup=channel_btn)
	else:
		if message.text[0]=='@':
			await panel_func.channel_delete(channel_id)
			await state.finish()
			await message.reply("Kanal muvaffaqiyatli o'chirildi", reply_markup=channel_btn)
		else:
			await message.reply("Kanal useri xato kiritildi\nIltimos userni @coder_admin ko'rinishida kiriting", reply_markup=channel_btn)

	await state.finish()

@dp.message_handler(text = "📋 Kanallar ro'yxati")
async def channelList(message: types.Message):
	if len(await panel_func.channel_list()) > 3:
		await message.reply(await panel_func.channel_list())
	else:
		await message.reply("Hozircha kanallar yo'q")

################################            REKLAMA          """"""""""""""""""""""

@dp.message_handler(text = "📤Reklama", user_id = Admin)
async def all_send(message: types.Message):
	await message.reply("Foydalanuvchilarga xabar yuborish bo'limi", reply_markup=reklama_btn)

@dp.message_handler(lambda message: message.text == "📨Forward xabar yuborish", user_id=Admin)
async def all_users(message: types.Message, state: FSMContext):
	markup = ReplyKeyboardMarkup(resize_keyboard=True)
	markup.add("🔙Orqaga qaytish")
	await message.answer("Forward yuboriladigan xabarni yuboring", reply_markup=markup)
	await From.forward_msg.set()

@dp.message_handler(state=From.forward_msg, text = "🔙Orqaga qaytish", content_types=ContentType.ANY, user_id=Admin)
async def all_users2(message: types.Message, state: FSMContext):
	await state.finish()
	await message.reply("Orqaga qaytildi", reply_markup=main_btn)

@dp.message_handler(state=From.forward_msg, content_types=ContentType.ANY, user_id=Admin)
async def all_users2(message: types.Message, state: FSMContext):
	await state.finish()
	markup = ReplyKeyboardMarkup(resize_keyboard=True)
	markup.add("🔙Orqaga qaytish")
	rows = sql.execute(f"SELECT user_id FROM users ").fetchall()
	soni = 0
	for row in rows:
		id = row[0]
		raqami = await forward_send_msg(from_chat_id=message.chat.id, message_id=message.message_id, chat_id=id)
		soni += raqami
		await asyncio.sleep(0.07)

	await message.answer(f"Xabar yuborish yakunlandi. Bu xabar {soni} ta odamga yuborildi", reply_markup=reklama_btn)


@dp.message_handler(lambda message: message.text == "📬Oddiy xabar yuborish", user_id=Admin)
async def all_users(message: types.Message, state: FSMContext):
	markup = ReplyKeyboardMarkup(resize_keyboard=True)
	markup.add("🔙Orqaga qaytish")
	await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring", reply_markup=markup)
	await From.send_msg.set()

@dp.message_handler(state=From.send_msg, text = "🔙Orqaga qaytish", content_types=ContentType.ANY, user_id=Admin)
async def all_users2(message: types.Message, state: FSMContext):
	await state.finish()
	await message.reply("Orqaga qaytildi", reply_markup=main_btn)

@dp.message_handler(state=From.send_msg, content_types=ContentType.ANY, user_id=Admin)
async def all_users2(message: types.Message, state: FSMContext):
	await state.finish()
	markup = ReplyKeyboardMarkup(resize_keyboard=True)
	markup.add("🔙Orqaga qaytish")
	rows = sql.execute(f"SELECT user_id FROM users ").fetchall()
	soni = 0
	for row in rows:
		id = row[0]
		raqami = await send_message_chats(from_chat_id=message.chat.id, message_id=message.message_id, chat_id=id)
		soni += raqami
		await asyncio.sleep(0.07)

	await message.answer(f"Xabar yuborish yakunlandi. Bu xabar {soni} ta odamga yuborildi", reply_markup=reklama_btn)


