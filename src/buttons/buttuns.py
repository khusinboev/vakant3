# ============================================
# src/buttons/buttuns.py - Aiogram 3.x
# ============================================
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Admin panel
main_btn = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊Statistika"), KeyboardButton(text="🔧Kanallar")],
        [KeyboardButton(text="📤Reklama")]
    ],
    resize_keyboard=True
)

channel_btn = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕Kanal qo'shish"), KeyboardButton(text="❌Kanalni olib tashlash")],
        [KeyboardButton(text="📋 Kanallar ro'yxati"), KeyboardButton(text="🔙Orqaga qaytish")]
    ],
    resize_keyboard=True
)

reklama_btn = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📨Forward xabar yuborish"), KeyboardButton(text="📬Oddiy xabar yuborish")],
        [KeyboardButton(text="🔙Orqaga qaytish")]
    ],
    resize_keyboard=True
)

# User menu
MM_btn = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💼 Ish qidirish"), KeyboardButton(text="🛠 Filtrni boshqarish")],
        [KeyboardButton(text="🗂 Saqlangan ishlar")]
    ],
    resize_keyboard=True
)

# Orqaga qaytish
back_btn = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]],
    resize_keyboard=True
)
