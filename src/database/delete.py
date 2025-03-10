import sqlite3

conn = sqlite3.connect("database.sqlite3")  # SQLite bazasiga ulanish
cursor = conn.cursor()

cursor.execute("DELETE FROM users")  # Barcha ma'lumotlarni o‘chirish
conn.commit()  # O‘zgarishlarni saqlash

print("Barcha ma'lumotlar o‘chirildi!")

conn.close()  # Ulanishni yopish
