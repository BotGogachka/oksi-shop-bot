import sqlite3
import os

def update_db():
    db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    
    # Проверяем, есть ли колонка image
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "image" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN image TEXT")
        print("✅ Добавлена колонка image в таблицу products")
    else:
        print("ℹ️ Колонка image уже существует")
    
    # Проверяем другие колонки для реферальной системы
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "ref_code" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN ref_code TEXT")
        print("✅ Добавлена колонка ref_code")
    
    if "referrer_id" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER")
        print("✅ Добавлена колонка referrer_id")
    
    if "ref_bonus" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN ref_bonus INTEGER DEFAULT 0")
        print("✅ Добавлена колонка ref_bonus")
    
    # Проверяем колонки в таблице accounts
    cursor.execute("PRAGMA table_info(accounts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "buyer_id" not in columns:
        cursor.execute("ALTER TABLE accounts ADD COLUMN buyer_id INTEGER")
        print("✅ Добавлена колонка buyer_id")
    
    if "buy_date" not in columns:
        cursor.execute("ALTER TABLE accounts ADD COLUMN buy_date TEXT")
        print("✅ Добавлена колонка buy_date")
    
    db.commit()
    db.close()
    print("✅ База данных обновлена!")

if __name__ == "__main__":
    update_db()