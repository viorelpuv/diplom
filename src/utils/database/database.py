# database.py — SQLite версия
import sqlite3
import json
from datetime import datetime

DB_PATH = 'brt_db.sql'

def get_db():
    """Получить соединение с БД SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Создать таблицы при первом запуске."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            phone TEXT UNIQUE,
            password_hash TEXT,
            first_name TEXT,
            last_name TEXT,
            middle_name TEXT,
            birth_date TEXT,
            citizenship TEXT,
            document_type TEXT,
            document_series TEXT,
            document_number TEXT,
            bonus_points INTEGER DEFAULT 0,
            loyalty_level TEXT DEFAULT 'none',
            language TEXT DEFAULT 'ru',
            currency TEXT DEFAULT 'RUB',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            city TEXT,
            country TEXT,
            timezone TEXT DEFAULT 'Europe/Moscow',
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departure_station_id INTEGER NOT NULL,
            arrival_station_id INTEGER NOT NULL,
            distance_km REAL,
            duration_minutes INTEGER,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (departure_station_id) REFERENCES stations(id),
            FOREIGN KEY (arrival_station_id) REFERENCES stations(id)
        );

        CREATE TABLE IF NOT EXISTS trains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            name TEXT,
            type TEXT NOT NULL,
            operator TEXT
        );

        CREATE TABLE IF NOT EXISTS wagons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            train_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            type TEXT NOT NULL,
            class TEXT NOT NULL,
            total_seats INTEGER NOT NULL,
            FOREIGN KEY (train_id) REFERENCES trains(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wagon_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            position TEXT,
            has_table INTEGER DEFAULT 0,
            near_toilet INTEGER DEFAULT 0,
            FOREIGN KEY (wagon_id) REFERENCES wagons(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            train_id INTEGER NOT NULL,
            departure_datetime TEXT NOT NULL,
            arrival_datetime TEXT NOT NULL,
            price_sitting REAL DEFAULT 0,
            price_reserved_seat REAL DEFAULT 0,
            price_compartment REAL DEFAULT 0,
            price_luxury REAL DEFAULT 0,
            price_soft REAL DEFAULT 0,
            price_sv REAL DEFAULT 0,
            service_fee REAL DEFAULT 0,
            status TEXT DEFAULT 'scheduled',
            delay_minutes INTEGER DEFAULT 0,
            FOREIGN KEY (route_id) REFERENCES routes(id),
            FOREIGN KEY (train_id) REFERENCES trains(id)
        );

        CREATE TABLE IF NOT EXISTS trip_seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            seat_id INTEGER NOT NULL,
            is_available INTEGER DEFAULT 1,
            FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
            FOREIGN KEY (seat_id) REFERENCES seats(id),
            UNIQUE(trip_id, seat_id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'RUB',
            payment_method TEXT,
            promo_code TEXT,
            paid_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            trip_id INTEGER NOT NULL,
            seat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            passenger_type TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'active',
            ticket_number TEXT NOT NULL UNIQUE,
            refund_amount REAL,
            refunded_at TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (trip_id) REFERENCES trips(id),
            FOREIGN KEY (seat_id) REFERENCES seats(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            gateway TEXT,
            external_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_station_id INTEGER NOT NULL,
            to_station_id INTEGER NOT NULL,
            departure_date TEXT NOT NULL,
            passengers_json TEXT,
            class TEXT,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (from_station_id) REFERENCES stations(id),
            FOREIGN KEY (to_station_id) REFERENCES stations(id)
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            is_active INTEGER DEFAULT 1,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            unsubscribed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_tickets_order ON tickets(order_id);
        CREATE INDEX IF NOT EXISTS idx_tickets_trip ON tickets(trip_id);
        CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
        CREATE INDEX IF NOT EXISTS idx_trips_departure ON trips(departure_datetime);
        CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history(user_id);
    """)
    
    conn.commit()
    conn.close()


# ============================================
# USERS
# ============================================
def save_passenger(data):
    """Сохраняет/обновляет данные пассажира. Возвращает user_id."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (first_name, last_name, middle_name, birth_date, 
                               document_type, document_number, citizenship, phone, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET 
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                middle_name = excluded.middle_name,
                birth_date = excluded.birth_date,
                document_type = excluded.document_type,
                document_number = excluded.document_number,
                citizenship = excluded.citizenship,
                phone = excluded.phone
        """, (
            data.get('first_name'),
            data.get('last_name'),
            data.get('middle_name'),
            data.get('birth_date'),
            data.get('document_type'),
            data.get('document_number'),
            data.get('citizenship', 'Россия'),
            data.get('phone'),
            data.get('email')
        ))
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except Exception as e:
        print(f"DB Error (save_passenger): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def get_user_by_document(doc_type, doc_number):
    """Найти пользователя по типу и номеру документа."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM users WHERE document_type = ? AND document_number = ?
        """, (doc_type, doc_number))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


def get_user_by_id(user_id):
    """Получить пользователя по ID."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


# ============================================
# ORDERS
# ============================================
def create_order(order_number, user_id, total_amount):
    """Создаёт заказ. Возвращает order_id."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO orders (order_number, user_id, status, total_amount, expires_at)
            VALUES (?, ?, 'pending', ?, datetime('now', '+20 minutes'))
        """, (order_number, user_id, total_amount))
        order_id = cursor.lastrowid
        conn.commit()
        return order_id
    except Exception as e:
        print(f"DB Error (create_order): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def update_order_status(order_id, status, paid_at=None):
    """Обновить статус заказа."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if status == 'paid':
            cursor.execute("""
                UPDATE orders SET status = 'paid', paid_at = datetime('now') WHERE id = ?
            """, (order_id,))
        else:
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()
    except Exception as e:
        print(f"DB Error (update_order_status): {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def get_order(order_id):
    """Получить заказ по ID."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


def get_order_by_number(order_number):
    """Получить заказ по номеру."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


# ============================================
# TICKETS
# ============================================
def save_ticket(order_id, ticket_data):
    """Сохраняет билет и обновляет доступность места."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO tickets (order_id, trip_id, seat_id, user_id, passenger_type, price, ticket_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            ticket_data.get('trip_id'),
            ticket_data.get('seat_id'),
            ticket_data.get('user_id'),
            ticket_data.get('passenger_type', 'adult'),
            ticket_data.get('price'),
            ticket_data.get('ticket_number')
        ))
        ticket_id = cursor.lastrowid
        
        cursor.execute("""
            UPDATE trip_seats SET is_available = 0 
            WHERE trip_id = ? AND seat_id = ?
        """, (ticket_data.get('trip_id'), ticket_data.get('seat_id')))
        
        conn.commit()
        return ticket_id
    except Exception as e:
        print(f"DB Error (save_ticket): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def get_tickets_by_order(order_id):
    """Получить все билеты заказа."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT t.*, s.number as seat_number, w.number as wagon_number, 
                   w.type as wagon_type, tr.departure_datetime, tr.arrival_datetime
            FROM tickets t
            JOIN seats s ON t.seat_id = s.id
            JOIN wagons w ON s.wagon_id = w.id
            JOIN trips tr ON t.trip_id = tr.id
            WHERE t.order_id = ?
        """, (order_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def update_ticket_status(ticket_id, status, refund_amount=None):
    """Обновить статус билета."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if status == 'refunded' and refund_amount:
            cursor.execute("""
                UPDATE tickets SET status = 'refunded', refund_amount = ?, refunded_at = datetime('now') 
                WHERE id = ?
            """, (refund_amount, ticket_id))
        else:
            cursor.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.commit()
    except Exception as e:
        print(f"DB Error (update_ticket_status): {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# ============================================
# TRANSACTIONS
# ============================================
def save_transaction(order_id, amount, trans_type, gateway, external_id, status='success'):
    """Сохраняет транзакцию."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO transactions (order_id, amount, type, gateway, external_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, amount, trans_type, gateway, external_id, status))
        transaction_id = cursor.lastrowid
        conn.commit()
        return transaction_id
    except Exception as e:
        print(f"DB Error (save_transaction): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# SEARCH HISTORY
# ============================================
def save_search_history(from_station_id, to_station_id, departure_date, passengers, user_id=None):
    """Сохраняет историю поиска."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO search_history (user_id, from_station_id, to_station_id, departure_date, passengers_json)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, from_station_id, to_station_id, departure_date, json.dumps(passengers)))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"DB Error (save_search_history): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def get_search_history(user_id=None, limit=10):
    """Получить историю поиска."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if user_id:
            cursor.execute("""
                SELECT sh.*, fs.name as from_name, ts.name as to_name
                FROM search_history sh
                JOIN stations fs ON sh.from_station_id = fs.id
                JOIN stations ts ON sh.to_station_id = ts.id
                WHERE sh.user_id = ?
                ORDER BY sh.searched_at DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            cursor.execute("""
                SELECT sh.*, fs.name as from_name, ts.name as to_name
                FROM search_history sh
                JOIN stations fs ON sh.from_station_id = fs.id
                JOIN stations ts ON sh.to_station_id = ts.id
                ORDER BY sh.searched_at DESC
                LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# ============================================
# STATIONS
# ============================================
def get_station_by_name(name):
    """Найти станцию по названию или коду."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM stations WHERE name LIKE ? OR code = ?
        """, (f"%{name}%", name))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


def get_all_stations():
    """Получить все активные станции."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM stations WHERE is_active = 1")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# ============================================
# TRIPS
# ============================================
def get_trip_by_id(trip_id):
    """Получить поездку по ID."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT t.*, r.departure_station_id, r.arrival_station_id,
                   tr.number as train_number, tr.name as train_name
            FROM trips t
            JOIN routes r ON t.route_id = r.id
            JOIN trains tr ON t.train_id = tr.id
            WHERE t.id = ?
        """, (trip_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


def get_available_seats(trip_id):
    """Получить доступные места для поездки."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.*, w.number as wagon_number, w.type as wagon_type
            FROM trip_seats ts
            JOIN seats s ON ts.seat_id = s.id
            JOIN wagons w ON s.wagon_id = w.id
            WHERE ts.trip_id = ? AND ts.is_available = 1
        """, (trip_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# ============================================
# SUBSCRIPTIONS
# ============================================
def subscribe_email(email):
    """Подписать email на рассылку."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subscriptions (email, is_active) 
            VALUES (?, 1)
            ON CONFLICT(email) DO UPDATE SET is_active = 1, unsubscribed_at = NULL
        """, (email,))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error (subscribe_email): {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def unsubscribe_email(email):
    """Отписать email от рассылки."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE subscriptions SET is_active = 0, unsubscribed_at = datetime('now')
            WHERE email = ?
        """, (email,))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error (unsubscribe_email): {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================
# STATIONS
# ============================================
def save_station(code, name, city=None, country=None, timezone='Europe/Moscow'):
    """Сохраняет или обновляет станцию."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO stations (code, name, city, country, timezone)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                city = excluded.city,
                country = excluded.country,
                timezone = excluded.timezone
        """, (code, name, city, country, timezone))
        
        conn.commit()
        
        # Всегда получаем id через SELECT
        cursor.execute("SELECT id FROM stations WHERE code = ?", (code,))
        row = cursor.fetchone()
        return row['id'] if row else None
        
    except Exception as e:
        print(f"DB Error (save_station): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# ROUTES
# ============================================
def save_route(departure_station_id, arrival_station_id, distance_km=None, duration_minutes=None):
    """Сохраняет маршрут."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM routes 
            WHERE departure_station_id = ? AND arrival_station_id = ?
        """, (departure_station_id, arrival_station_id))
        existing = cursor.fetchone()
        
        if existing:
            route_id = existing['id']
            if distance_km or duration_minutes:
                cursor.execute("""
                    UPDATE routes SET distance_km = ?, duration_minutes = ? WHERE id = ?
                """, (distance_km, duration_minutes, route_id))
        else:
            cursor.execute("""
                INSERT INTO routes (departure_station_id, arrival_station_id, distance_km, duration_minutes)
                VALUES (?, ?, ?, ?)
            """, (departure_station_id, arrival_station_id, distance_km, duration_minutes))
            route_id = cursor.lastrowid
        
        conn.commit()
        return route_id
    except Exception as e:
        print(f"DB Error (save_route): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# TRAINS
# ============================================
def save_train(number, name=None, train_type=None, operator=None):
    """Сохраняет или обновляет поезд."""
    if not number or number.strip() == '':
        print(f"     ⚠️ save_train: пустой номер поезда")
        return None
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Пробуем вставить
        cursor.execute("""
            INSERT INTO trains (number, name, type, operator)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(number) DO UPDATE SET
                name = COALESCE(excluded.name, trains.name),
                type = COALESCE(excluded.type, trains.type),
                operator = COALESCE(excluded.operator, trains.operator)
        """, (number, name or '', train_type or 'passenger', operator or ''))
        
        conn.commit()
        
        # Получаем id — ВСЕГДА через SELECT
        cursor.execute("SELECT id FROM trains WHERE number = ?", (number,))
        row = cursor.fetchone()
        
        if row:
            train_id = row['id']
            print(f"     save_train: {number} → id={train_id}")
            return train_id
        else:
            print(f"     save_train: {number} → НЕ НАЙДЕН после вставки!")
            return None
            
    except Exception as e:
        print(f"     ❌ save_train error: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# WAGONS
# ============================================
def save_wagon(train_id, number, wagon_type, wagon_class, total_seats):
    """Сохраняет вагон."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM wagons WHERE train_id = ? AND number = ?
        """, (train_id, number))
        existing = cursor.fetchone()
        
        if existing:
            wagon_id = existing['id']
            cursor.execute("""
                UPDATE wagons SET type = ?, class = ?, total_seats = ? WHERE id = ?
            """, (wagon_type, wagon_class, total_seats, wagon_id))
        else:
            cursor.execute("""
                INSERT INTO wagons (train_id, number, type, class, total_seats)
                VALUES (?, ?, ?, ?, ?)
            """, (train_id, number, wagon_type, wagon_class, total_seats))
            wagon_id = cursor.lastrowid
        
        conn.commit()
        return wagon_id
    except Exception as e:
        print(f"DB Error (save_wagon): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# SEATS
# ============================================
def save_seat(wagon_id, number, position=None):
    """Сохраняет место."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM seats WHERE wagon_id = ? AND number = ?
        """, (wagon_id, number))
        existing = cursor.fetchone()
        
        if existing:
            seat_id = existing['id']
            cursor.execute("UPDATE seats SET position = ? WHERE id = ?", (position, seat_id))
        else:
            cursor.execute("""
                INSERT INTO seats (wagon_id, number, position)
                VALUES (?, ?, ?)
            """, (wagon_id, number, position))
            seat_id = cursor.lastrowid
        
        conn.commit()
        return seat_id
    except Exception as e:
        print(f"DB Error (save_seat): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# TRIPS
# ============================================
def save_trip(route_id, train_id, departure_datetime, arrival_datetime, 
              prices_dict=None, service_fee=0):
    """Сохраняет или обновляет рейс с ценами по типам вагонов."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        prices_dict = prices_dict or {}
        
        cursor.execute("""
            SELECT id FROM trips 
            WHERE route_id = ? AND train_id = ? AND departure_datetime = ?
        """, (route_id, train_id, departure_datetime))
        existing = cursor.fetchone()
        
        if existing:
            trip_id = existing['id']
            cursor.execute("""
                UPDATE trips SET 
                    arrival_datetime = ?,
                    price_sitting = ?,
                    price_reserved_seat = ?,
                    price_compartment = ?,
                    price_luxury = ?,
                    price_soft = ?,
                    price_sv = ?,
                    service_fee = ?
                WHERE id = ?
            """, (
                arrival_datetime,
                prices_dict.get('sitting', 0),
                prices_dict.get('reserved_seat', 0),
                prices_dict.get('compartment', 0),
                prices_dict.get('luxury', 0),
                prices_dict.get('soft', 0),
                prices_dict.get('sv', 0),
                service_fee,
                trip_id
            ))
        else:
            cursor.execute("""
                INSERT INTO trips (route_id, train_id, departure_datetime, arrival_datetime,
                                   price_sitting, price_reserved_seat, price_compartment,
                                   price_luxury, price_soft, price_sv, service_fee)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                route_id, train_id, departure_datetime, arrival_datetime,
                prices_dict.get('sitting', 0),
                prices_dict.get('reserved_seat', 0),
                prices_dict.get('compartment', 0),
                prices_dict.get('luxury', 0),
                prices_dict.get('soft', 0),
                prices_dict.get('sv', 0),
                service_fee
            ))
            trip_id = cursor.lastrowid
        
        conn.commit()
        return trip_id
    except Exception as e:
        print(f"DB Error (save_trip): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# TRIP SEATS
# ============================================
def save_trip_seat(trip_id, seat_id, is_available=True):
    """Сохраняет доступность места для рейса."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO trip_seats (trip_id, seat_id, is_available)
            VALUES (?, ?, ?)
        """, (trip_id, seat_id, 1 if is_available else 0))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"DB Error (save_trip_seat): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


# ============================================
# ПОЛНОЕ СОХРАНЕНИЕ БИЛЕТА ИЗ API
# ============================================
def save_train_full(train_data, from_city, to_city):
    """Сохраняет полную информацию о поезде из API."""
    train_number = train_data.get('train_number', '')
    print(f"\n  📝 save_train_full: {train_number} | {from_city} → {to_city}")
    
    try:
        # 1. Станции
        from_code = from_city[:10].replace(' ', '_')
        to_code = to_city[:10].replace(' ', '_')
        
        print(f"     Станции: from_code={from_code}, to_code={to_code}")
        
        from_station_id = save_station(
            code=from_code,
            name=train_data.get('from_station', from_city),
            city=from_city
        )
        to_station_id = save_station(
            code=to_code,
            name=train_data.get('to_station', to_city),
            city=to_city
        )
        
        print(f"     Станции сохранены: from_id={from_station_id}, to_id={to_station_id}")
        
        if not from_station_id or not to_station_id:
            print(f"     ❌ Станции не сохранились!")
            return None
        
        # 2. Маршрут
        route_id = save_route(from_station_id, to_station_id)
        print(f"     Маршрут: route_id={route_id}")
        
        if not route_id:
            print(f"     ❌ Маршрут не сохранился!")
            return None
        
        # 3. Поезд
        train_id = save_train(
            number=train_number,
            name=train_data.get('train_name', ''),
            train_type='passenger'
        )
        print(f"     Поезд: train_id={train_id}")
        
        if not train_id:
            print(f"     ❌ Поезд не сохранился (номер: '{train_number}')!")
            return None
        
        # 4. Рейс
        dep_date = train_data.get('date', datetime.now().strftime('%Y-%m-%d'))
        prices = train_data.get('prices', {})

        # Собираем цены по типам вагонов
        prices_dict = {}
        for wagon_type, wagon_data in prices.items():
            if wagon_data.get('price', 0) > 0:
                prices_dict[wagon_type] = wagon_data['price']

        print(f"     Цены: {prices_dict}")

        trip_id = save_trip(
            route_id=route_id,
            train_id=train_id,
            departure_datetime=f"{dep_date} {train_data.get('departure', '00:00')}",
            arrival_datetime=f"{dep_date} {train_data.get('arrival', '00:00')}",
            prices_dict=prices_dict,
            service_fee=200
        )
        print(f"     Рейс: trip_id={trip_id}")
        
        if not trip_id:
            print(f"     ❌ Рейс не сохранился!")
            return None
        
        # 5. Вагоны и места
        prices = train_data.get('prices', {})
        print(f"     Вагоны: {list(prices.keys())}")
        
        wagon_num = 1
        for wagon_type, wagon_data in prices.items():
            if wagon_data.get('price', 0) <= 0:
                continue
            
            wagon_id = save_wagon(
                train_id=train_id,
                number=str(wagon_num),
                wagon_type=wagon_type,
                wagon_class='economy',
                total_seats=wagon_data.get('total_seats', wagon_data.get('free_seats', 36))
            )
            print(f"     Вагон {wagon_num}: wagon_id={wagon_id}, тип={wagon_type}")
            
            if wagon_id:
                for seat_num in range(1, min(wagon_data.get('free_seats', 36) + 1, 61)):
                    seat_id = save_seat(wagon_id, str(seat_num))
                    if seat_id:
                        save_trip_seat(trip_id, seat_id, True)
                wagon_num += 1
        
        print(f"     ✅ Поезд {train_number} сохранён, trip_id={trip_id}")
        return trip_id
        
    except Exception as e:
        print(f"     ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None