import sqlite3

db = sqlite3.connect('database.sqlite3')
sql = db.cursor()
sql.execute("DELETE FROM users")  # Barcha ma'lumotlarni o‘chirish
db.commit()


print("Barcha ma'lumotlar o‘chirildi!")
