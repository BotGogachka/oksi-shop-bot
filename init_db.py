import sqlite3
import os

def init_db():
    db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    
    # Создаём таблицу пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            join_date TEXT
        )
    ''')
    
    # Создаём таблицу товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            stock INTEGER
        )
    ''')
    
    # Создаём таблицу аккаунтов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            data TEXT,
            status TEXT DEFAULT 'available',
            buyer_id INTEGER,
            buy_date TEXT
        )
    ''')
    
    db.commit()
    db.close()
    print("✅ База данных создана!")
    print("📁 Путь:", db_path)

if __name__ == "__main__":
    init_db()