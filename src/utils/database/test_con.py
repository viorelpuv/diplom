# test_db.py — тест подключения к SQLite
import os
from database import init_db, get_db, save_passenger, create_order, save_ticket, save_transaction

def test_connection():
    """Тестируем подключение и создание таблиц."""
    
    # Удаляем старую базу если есть
    if os.path.exists('brt_db.sql'):
        os.remove('brt_db.sql')
        print("✅ Старая база удалена")
    
    # 1. Создаём таблицы
    print("\n1. Создание таблиц...")
    try:
        init_db()
        print("✅ Таблицы созданы")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    # 2. Проверяем соединение
    print("\n2. Проверка соединения...")
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"✅ Таблиц в БД: {len(tables)}")
        for table in tables:
            print(f"   - {table['name']}")
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    # 3. Сохраняем тестового пассажира
    print("\n3. Сохранение пассажира...")
    try:
        passenger_data = {
            'first_name': 'Иван',
            'last_name': 'Тестов',
            'middle_name': 'Тестович',
            'birth_date': '1990-01-01',
            'document_type': 'passport_rf',
            'document_number': '1234567890',
            'phone': '+79001234567',
            'email': 'test@example.com',
            'citizenship': 'Россия'
        }
        user_id = save_passenger(passenger_data)
        if user_id:
            print(f"✅ Пассажир сохранён, user_id = {user_id}")
        else:
            print("❌ Не удалось сохранить")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    # 4. Создаём заказ
    print("\n4. Создание заказа...")
    try:
        order_number = f"BRT-TEST-{__import__('datetime').datetime.now().strftime('%Y%m%d%H%M%S')}"
        order_id = create_order(order_number, user_id, 5000.00)
        if order_id:
            print(f"✅ Заказ создан, order_id = {order_id}, номер = {order_number}")
        else:
            print("❌ Не удалось создать заказ")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    # 5. Проверяем данные в таблицах
    print("\n5. Проверка данных...")
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Пользователи
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        users_count = cursor.fetchone()['cnt']
        print(f"✅ Пользователей: {users_count}")
        
        # Заказы
        cursor.execute("SELECT COUNT(*) as cnt FROM orders")
        orders_count = cursor.fetchone()['cnt']
        print(f"✅ Заказов: {orders_count}")
        
        # Билеты
        cursor.execute("SELECT COUNT(*) as cnt FROM tickets")
        tickets_count = cursor.fetchone()['cnt']
        print(f"✅ Билетов: {tickets_count}")
        
        # Транзакции
        cursor.execute("SELECT COUNT(*) as cnt FROM transactions")
        trans_count = cursor.fetchone()['cnt']
        print(f"✅ Транзакций: {trans_count}")
        
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    print("\n" + "="*50)
    print("🎉 ТЕСТ ПРОЙДЕН УСПЕШНО!")
    print("="*50)
    print(f"\nБаза данных: {os.path.abspath('brt_db.sql')}")
    print(f"Размер: {os.path.getsize('brt_db.sql')} байт")
    
    return True


if __name__ == '__main__':
    test_connection()