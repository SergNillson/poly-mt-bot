"""
Тест создания базы данных
"""
import os
import sys

print("=" * 60)
print("ТЕСТ СОЗДАНИЯ БАЗЫ ДАННЫХ")
print("=" * 60)

# Проверяем структуру каталогов
print(f"\nТекущая директория: {os.getcwd()}")
print(f"Содержимое data/: {os.listdir('data') if os.path.exists('data') else 'папка не существует'}")

# Импортируем и создаем базу
try:
    from src.database.database import Database
    
    print("\n✅ Импорт Database успешен")
    
    db_path = 'data/trading.db'
    print(f"\nСоздаем базу данных: {db_path}")
    
    db = Database(db_path)
    
    print(f"✅ База данных создана!")
    print(f"\nПроверяем файл: {os.path.exists(db_path)}")
    
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"✅ Файл существует, размер: {size} байт")
    else:
        print("❌ ФАЙЛ НЕ СОЗДАН!")
        
    # Проверяем содержимое папки data
    print(f"\nСодержимое data/ после создания:")
    for item in os.listdir('data'):
        full_path = os.path.join('data', item)
        size = os.path.getsize(full_path) if os.path.isfile(full_path) else 'DIR'
        print(f"  - {item} ({size})")
    
except Exception as e:
    print(f"❌ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)