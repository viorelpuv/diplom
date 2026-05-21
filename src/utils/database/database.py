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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            permissions TEXT DEFAULT '[]',
            is_superadmin INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            success INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
                         
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            discount_percent INTEGER DEFAULT 10,
            discount_amount REAL DEFAULT 0,
            min_order_amount REAL DEFAULT 0,
            max_uses INTEGER DEFAULT 0,
            used_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
                         
        CREATE TABLE IF NOT EXISTS admin_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_tickets_order ON tickets(order_id);
        CREATE INDEX IF NOT EXISTS idx_tickets_trip ON tickets(trip_id);
        CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
        CREATE INDEX IF NOT EXISTS idx_trips_departure ON trips(departure_datetime);
        CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history(user_id);
        
        CREATE INDEX IF NOT EXISTS idx_admins_user ON admins(user_id);
        CREATE INDEX IF NOT EXISTS idx_login_history_user ON login_history(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """)
    
    # Создаём супер-админа
    try:
        cursor.execute("SELECT id FROM admins WHERE is_superadmin = 1")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO admins (user_id, permissions, is_superadmin, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (1, '["all"]', 1))
            print("✅ Супер-админ создан (user_id=1, права=all)")
        else:
            print("ℹ️ Супер-админ уже существует")
    except Exception as e:
        print(f"⚠️ Ошибка создания админа: {e}")
    
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
            INSERT INTO tickets (order_id, trip_id, seat_id, user_id, passenger_type, price, ticket_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
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
        
        # Обновляем доступность места
        if ticket_data.get('trip_id') and ticket_data.get('seat_id'):
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

def reserve_seats(trip_id, seat_ids):
    """Временно забронировать места."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        for seat_id in seat_ids:
            cursor.execute("""
                UPDATE trip_seats SET is_available = 0 
                WHERE trip_id = ? AND seat_id = ? AND is_available = 1
            """, (trip_id, seat_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error (reserve_seats): {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def release_seats(trip_id, seat_ids):
    """Освободить забронированные места."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        for seat_id in seat_ids:
            cursor.execute("""
                UPDATE trip_seats SET is_available = 1 
                WHERE trip_id = ? AND seat_id = ?
            """, (trip_id, seat_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error (release_seats): {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def release_expired_orders():
    """Освободить места по истёкшим заказам."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Находим истёкшие заказы
        cursor.execute("""
            SELECT id FROM orders 
            WHERE status = 'pending' AND expires_at < datetime('now')
        """)
        expired_orders = [row['id'] for row in cursor.fetchall()]
        
        for order_id in expired_orders:
            # Находим билеты заказа
            cursor.execute("""
                SELECT t.seat_id, t.trip_id FROM tickets t
                WHERE t.order_id = ?
            """, (order_id,))
            tickets = cursor.fetchall()
            
            # Освобождаем места
            for ticket in tickets:
                cursor.execute("""
                    UPDATE trip_seats SET is_available = 1 
                    WHERE trip_id = ? AND seat_id = ?
                """, (ticket['trip_id'], ticket['seat_id']))
            
            # Отменяем заказ
            cursor.execute("UPDATE orders SET status = 'expired' WHERE id = ?", (order_id,))
            # Отменяем билеты
            cursor.execute("UPDATE tickets SET status = 'cancelled' WHERE order_id = ?", (order_id,))
        
        conn.commit()
        return len(expired_orders)
    except Exception as e:
        print(f"DB Error (release_expired_orders): {e}")
        conn.rollback()
        return 0
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
    
    try:
        # 1. Станции
        from_code = from_city[:10].replace(' ', '_')
        to_code = to_city[:10].replace(' ', '_')
        
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
        
        if not from_station_id or not to_station_id:
            return None
        
        # 2. Маршрут
        route_id = save_route(from_station_id, to_station_id)
        
        if not route_id:
            return None
        
        # 3. Поезд
        train_id = save_train(
            number=train_number,
            name=train_data.get('train_name', ''),
            train_type='passenger'
        )
        
        if not train_id:
            return None
        
        # 4. Рейс
        dep_date = train_data.get('date', datetime.now().strftime('%Y-%m-%d'))
        prices = train_data.get('prices', {})

        prices_dict = {}
        for wagon_type, wagon_data in prices.items():
            if wagon_data.get('price', 0) > 0:
                prices_dict[wagon_type] = wagon_data['price']

        trip_id = save_trip(
            route_id=route_id,
            train_id=train_id,
            departure_datetime=f"{dep_date} {train_data.get('departure', '00:00')}",
            arrival_datetime=f"{dep_date} {train_data.get('arrival', '00:00')}",
            prices_dict=prices_dict,
            service_fee=200
        )
        
        if not trip_id:
            return None
        
        # 5. Вагоны и места — ОПТИМИЗИРОВАННАЯ МАССОВАЯ ВСТАВКА
        prices = train_data.get('prices', {})
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            wagon_num = 1
            all_seats_to_insert = []  # для массовой вставки мест
            all_trip_seats_to_insert = []  # для массовой вставки trip_seats
            
            for wagon_type, wagon_data in prices.items():
                if wagon_data.get('price', 0) <= 0:
                    continue
                
                # Сохраняем вагон
                cursor.execute("""
                    SELECT id FROM wagons WHERE train_id = ? AND number = ?
                """, (train_id, str(wagon_num)))
                existing_wagon = cursor.fetchone()
                
                total_seats = wagon_data.get('total_seats', wagon_data.get('free_seats', 36))
                
                if existing_wagon:
                    wagon_id = existing_wagon['id']
                    cursor.execute("""
                        UPDATE wagons SET type = ?, class = ?, total_seats = ? WHERE id = ?
                    """, (wagon_type, 'economy', total_seats, wagon_id))
                else:
                    cursor.execute("""
                        INSERT INTO wagons (train_id, number, type, class, total_seats)
                        VALUES (?, ?, ?, ?, ?)
                    """, (train_id, str(wagon_num), wagon_type, 'economy', total_seats))
                    wagon_id = cursor.lastrowid
                
                if wagon_id:
                    # Собираем места для массовой вставки
                    free_seats = min(wagon_data.get('free_seats', 36), 60)
                    for seat_num in range(1, free_seats + 1):
                        all_seats_to_insert.append((wagon_id, str(seat_num), None))
                    
                wagon_num += 1
            
            # Массовая вставка мест через INSERT OR IGNORE
            if all_seats_to_insert:
                cursor.executemany("""
                    INSERT OR IGNORE INTO seats (wagon_id, number, position)
                    VALUES (?, ?, ?)
                """, all_seats_to_insert)
            
            # Получаем ID всех мест для этих вагонов
            cursor.execute("""
                SELECT s.id as seat_id, s.number, w.number as wagon_number
                FROM seats s
                JOIN wagons w ON s.wagon_id = w.id
                WHERE w.train_id = ? AND w.number IN ({})
            """.format(','.join(['?'] * wagon_num)), [train_id] + [str(i) for i in range(1, wagon_num)])
            
            seat_rows = cursor.fetchall()
            
            # Массовая вставка trip_seats
            for row in seat_rows:
                all_trip_seats_to_insert.append((trip_id, row['seat_id'], 1))
            
            if all_trip_seats_to_insert:
                cursor.executemany("""
                    INSERT OR IGNORE INTO trip_seats (trip_id, seat_id, is_available)
                    VALUES (?, ?, ?)
                """, all_trip_seats_to_insert)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()
        
        return trip_id
        
    except Exception as e:
        return None
    

# ============================================
# AUTH
# ============================================
def register_user(email, password, first_name=None, last_name=None, phone=None):
    """Регистрация нового пользователя. Если email уже есть — обновляет пароль."""
    from utils.hasher import generate_hash
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        password_hash = generate_hash(password)
        
        cursor.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
        existing = cursor.fetchone()
        
        if existing:
            # Пользователь уже есть — обновляем пароль
            cursor.execute("""
                UPDATE users SET 
                    password_hash = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (password_hash, existing['id']))
            user_id = existing['id']
        else:
            # Новый пользователь
            cursor.execute("""
                INSERT INTO users (email, password_hash, first_name, last_name, phone)
                VALUES (?, ?, ?, ?, ?)
            """, (email, password_hash, first_name, last_name, phone))
            user_id = cursor.lastrowid
        
        conn.commit()
        return user_id
    except Exception as e:
        print(f"DB Error (register_user): {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def login_user(email, password):
    """Проверка логина и пароля. Возвращает user_id или None."""
    from utils.hasher import check_hash
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user or not user['password_hash']:
            return None
        
        if check_hash(user['password_hash'], password):
            # Обновляем last_login
            cursor.execute("""
                UPDATE users SET 
                    phone = COALESCE(users.phone, '')  -- заглушка, last_login не храним в этой версии
                WHERE id = ?
            """, (user['id'],))
            conn.commit()
            return user['id']
        
        return None
    except Exception as e:
        print(f"DB Error (login_user): {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def save_login_history(user_id, ip_address=None, user_agent=None, success=True):
    """Сохраняет запись о входе."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO login_history (user_id, ip_address, user_agent, success)
            VALUES (?, ?, ?, ?)
        """, (user_id, ip_address, user_agent, 1 if success else 0))
        conn.commit()
    except Exception as e:
        print(f"DB Error (save_login_history): {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def update_profile(user_id, data):
    """Обновляет профиль пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        fields = []
        values = []
        
        allowed_fields = ['first_name', 'last_name', 'middle_name', 'birth_date', 
                          'phone', 'citizenship', 'gender']
        
        for field in allowed_fields:
            if field in data and data[field]:
                fields.append(f"{field} = ?")
                values.append(data[field])
        
        if not fields:
            return False
        
        fields.append("updated_at = datetime('now')")
        values.append(user_id)
        
        query = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error (update_profile): {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def change_password(user_id, current_password, new_password):
    """Меняет пароль пользователя. Возвращает (success, message)."""
    from utils.hasher import generate_hash, check_hash
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return False, 'Пользователь не найден'
        
        if not check_hash(user['password_hash'], current_password):
            return False, 'Неверный текущий пароль'
        
        new_hash = generate_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?", 
                       (new_hash, user_id))
        conn.commit()
        return True, 'Пароль изменён'
    except Exception as e:
        print(f"DB Error (change_password): {e}")
        conn.rollback()
        return False, 'Ошибка'
    finally:
        cursor.close()
        conn.close()


def get_user_tickets(user_id):
    """Получает все билеты пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT t.*, o.order_number, 
                   s.number as seat, w.number as wagon, w.type as wagon_type,
                   tr.departure_datetime, tr.arrival_datetime, tr2.number as train_number,
                   st_from.city as from_city, st_to.city as to_city
            FROM tickets t
            JOIN orders o ON t.order_id = o.id
            LEFT JOIN seats s ON t.seat_id = s.id
            LEFT JOIN wagons w ON s.wagon_id = w.id
            LEFT JOIN trips tr ON t.trip_id = tr.id
            LEFT JOIN trains tr2 ON tr.train_id = tr2.id
            LEFT JOIN routes r ON tr.route_id = r.id
            LEFT JOIN stations st_from ON r.departure_station_id = st_from.id
            LEFT JOIN stations st_to ON r.arrival_station_id = st_to.id
            WHERE o.user_id = ?
            ORDER BY t.created_at DESC
        """, (user_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_user_login_history(user_id, limit=20):
    """Получает историю входов пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ip_address, user_agent, success, created_at
            FROM login_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_user_bonus(user_id):
    """Получает бонусную информацию пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT bonus_points, loyalty_level FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            return {
                'points': user['bonus_points'] or 0,
                'level': user['loyalty_level'] or 'none'
            }
        return {'points': 0, 'level': 'none'}
    finally:
        cursor.close()
        conn.close()

# ============================================
# ADMIN
# ============================================
def is_admin(user_id):
    """Проверяет, является ли пользователь админом."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_superadmin FROM admins WHERE user_id = ?", (user_id,))
        admin = cursor.fetchone()
        
        if not admin:
            return False, False
        
        return True, bool(admin['is_superadmin'])
    finally:
        cursor.close()
        conn.close()


def get_dashboard_stats():
    """Получает статистику для дашборда."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) as revenue FROM orders WHERE date(created_at) = date('now') AND status = 'paid'")
        revenue = cursor.fetchone()['revenue']
        
        cursor.execute("SELECT COUNT(*) as cnt FROM tickets")
        tickets = cursor.fetchone()['cnt']
        
        cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'pending'")
        orders = cursor.fetchone()['cnt']
        
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        users = cursor.fetchone()['cnt']
        
        return {
            'revenue': revenue,
            'tickets_sold': tickets,
            'active_orders': orders,
            'total_users': users
        }
    finally:
        cursor.close()
        conn.close()


def get_all_orders(limit=50):
    """Получает все заказы."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_all_users(limit=100):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email, phone, first_name, last_name, COALESCE(is_active, 1) as is_active, created_at FROM users ORDER BY id ASC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_all_trains(limit=100):
    """Получает все поезда."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM trains ORDER BY number LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_all_stations(limit=100):
    """Получает все станции."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM stations ORDER BY name LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_all_tickets(limit=100):
    """Получает все билеты."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_all_admins():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT a.id, a.user_id, a.is_superadmin, a.created_at,
                   u.email, u.first_name, u.last_name
            FROM admins a 
            JOIN users u ON a.user_id = u.id
            ORDER BY a.is_superadmin DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

# ============================================
# PROMOCODES
# ============================================
def get_all_promocodes():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def create_promocode(code, discount_percent=10, discount_amount=0, min_order=0, max_uses=0, expires_at=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO promocodes (code, discount_percent, discount_amount, min_order_amount, max_uses, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code, discount_percent, discount_amount, min_order, max_uses, expires_at))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Ошибка создания промокода: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

def delete_promocode(promo_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM promocodes WHERE id = ?", (promo_id,))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

# ============================================
# ADMIN LOGS
# ============================================
def get_admin_logs(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT lh.*, u.email 
            FROM login_history lh 
            JOIN users u ON lh.user_id = u.id 
            JOIN admins a ON u.id = a.user_id 
            ORDER BY lh.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

# ============================================
# ADMIN USERS MANAGEMENT
# ============================================

def toggle_user_active(user_id, is_active):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (is_active, user_id))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

# ============================================
# ADMIN ADMINS MANAGEMENT
# ============================================
def add_admin(user_id, permissions='["all"]', is_superadmin=0):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO admins (user_id, permissions, is_superadmin)
            VALUES (?, ?, ?)
        """, (user_id, permissions, is_superadmin))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def remove_admin(user_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

# ============================================
# REPORTS
# ============================================
def get_sales_report(start_date=None, end_date=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT date(o.created_at) as date, 
                   COUNT(*) as tickets_sold, 
                   SUM(t.price) as revenue
            FROM tickets t
            JOIN orders o ON t.order_id = o.id
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND date(o.created_at) >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date(o.created_at) <= ?"
            params.append(end_date)
        query += " GROUP BY date(o.created_at) ORDER BY date(o.created_at) DESC LIMIT 30"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def get_tickets_by_date(date):
    """Получает билеты за конкретную дату."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT t.*, o.created_at as order_date,
                   st_from.city as from_city, st_to.city as to_city,
                   tr.departure_datetime as departure
            FROM tickets t
            JOIN orders o ON t.order_id = o.id
            JOIN trips tr ON t.trip_id = tr.id
            JOIN routes r ON tr.route_id = r.id
            JOIN stations st_from ON r.departure_station_id = st_from.id
            JOIN stations st_to ON r.arrival_station_id = st_to.id
            WHERE date(o.created_at) = ?
            ORDER BY o.created_at DESC
        """, (date,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def save_admin_action(admin_id, action, details=None, ip_address=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO admin_actions (admin_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        """, (admin_id, action, details, ip_address))
        conn.commit()
    except:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_admin_actions(limit=100):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT aa.*, u.email 
            FROM admin_actions aa 
            JOIN users u ON aa.admin_id = u.id 
            ORDER BY aa.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# ============================================
# SETTINGS
# ============================================
def get_settings():
    """Получить настройки системы."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM settings WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {
            'service_fee': 200,
            'payment_timeout': 20,
            'max_tickets_per_order': 5,
            'bonus_rate': 1,
            'bonus_value': 1,
            'bonus_register': 100,
            'min_bonus_order': 500,
            'max_bonus_percent': 30,
            'max_login_attempts': 5,
            'block_minutes': 30,
            'min_password_length': 6,
            'maintenance_mode': False,
            'maintenance_message': 'Сайт на техническом обслуживании'
        }
    finally:
        cursor.close()
        conn.close()


def save_settings(data):
    """Сохранить настройки системы."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM settings WHERE id = 1")
        if cursor.fetchone():
            cursor.execute("""
                UPDATE settings SET 
                    service_fee = ?, payment_timeout = ?, max_tickets_per_order = ?,
                    bonus_rate = ?, bonus_value = ?, bonus_register = ?,
                    min_bonus_order = ?, max_bonus_percent = ?,
                    max_login_attempts = ?, block_minutes = ?, min_password_length = ?,
                    maintenance_mode = ?, maintenance_message = ?
                WHERE id = 1
            """, (
                data.get('service_fee', 200),
                data.get('payment_timeout', 20),
                data.get('max_tickets_per_order', 5),
                data.get('bonus_rate', 1),
                data.get('bonus_value', 1),
                data.get('bonus_register', 100),
                data.get('min_bonus_order', 500),
                data.get('max_bonus_percent', 30),
                data.get('max_login_attempts', 5),
                data.get('block_minutes', 30),
                data.get('min_password_length', 6),
                data.get('maintenance_mode', 1 if data.get('maintenance_mode') else 0),
                data.get('maintenance_message', 'Сайт на техническом обслуживании')
            ))
        else:
            cursor.execute("""
                INSERT INTO settings (id, service_fee, payment_timeout, max_tickets_per_order,
                    bonus_rate, bonus_value, bonus_register, min_bonus_order, max_bonus_percent,
                    max_login_attempts, block_minutes, min_password_length,
                    maintenance_mode, maintenance_message)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('service_fee', 200),
                data.get('payment_timeout', 20),
                data.get('max_tickets_per_order', 5),
                data.get('bonus_rate', 1),
                data.get('bonus_value', 1),
                data.get('bonus_register', 100),
                data.get('min_bonus_order', 500),
                data.get('max_bonus_percent', 30),
                data.get('max_login_attempts', 5),
                data.get('block_minutes', 30),
                data.get('min_password_length', 6),
                data.get('maintenance_mode', 1 if data.get('maintenance_mode') else 0),
                data.get('maintenance_message', 'Сайт на техническом обслуживании')
            ))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка сохранения настроек: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================
# PROMO CHECK
# ============================================
def check_promocode(code, order_amount=0):
    """Проверить промокод и вернуть скидку."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM promocodes 
            WHERE code = ? AND is_active = 1 
            AND (expires_at IS NULL OR expires_at >= datetime('now'))
            AND (max_uses = 0 OR used_count < max_uses)
        """, (code,))
        
        promo = cursor.fetchone()
        if not promo:
            return {'valid': False, 'message': 'Промокод не найден или истёк'}
        
        promo = dict(promo)
        
        if promo['min_order_amount'] > 0 and order_amount < promo['min_order_amount']:
            return {
                'valid': False,
                'message': f'Минимальная сумма заказа: {promo["min_order_amount"]} ₽'
            }
        
        message = 'Промокод применён!'
        if promo['discount_percent']:
            message += f' Скидка {promo["discount_percent"]}%'
        elif promo['discount_amount']:
            message += f' Скидка {promo["discount_amount"]} ₽'
        
        return {
            'valid': True,
            'message': message,
            'discount_percent': promo['discount_percent'],
            'discount_amount': promo['discount_amount'],
            'promo_id': promo['id']
        }
    finally:
        cursor.close()
        conn.close()


def apply_promocode(promo_id):
    """Увеличить счётчик использований промокода."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE id = ?", (promo_id,))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def update_order_promo(order_id, promo_code):
    """Обновить промокод в заказе."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE orders SET promo_code = ? WHERE id = ?", (promo_code, order_id))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================
# BONUS
# ============================================
def get_user_total_spent(user_id):
    """Получить общую сумму покупок пользователя."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total_spent 
            FROM orders 
            WHERE user_id = ? AND status = 'paid'
        """, (user_id,))
        row = cursor.fetchone()
        return row['total_spent'] if row else 0
    finally:
        cursor.close()
        conn.close()


def calculate_loyalty_level(total_spent):
    """Рассчитать уровень лояльности на основе потраченной суммы."""
    if total_spent >= 200000:
        return 'platinum'
    elif total_spent >= 70000:
        return 'gold'
    elif total_spent >= 20000:
        return 'silver'
    return 'none'


def update_user_loyalty(user_id):
    """Обновить уровень лояльности пользователя."""
    total_spent = get_user_total_spent(user_id)
    level = calculate_loyalty_level(total_spent)
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users SET loyalty_level = ?, updated_at = datetime('now') 
            WHERE id = ?
        """, (level, user_id))
        conn.commit()
        print(f"DEBUG: loyalty_level обновлён: user_id={user_id}, level={level}, total_spent={total_spent}")
        return level
    except Exception as e:
        print(f"ERROR update_user_loyalty: {e}")
        conn.rollback()
        return 'none'
    finally:
        cursor.close()
        conn.close()


def add_bonus_points(user_id, amount_paid):
    """Начислить бонусные баллы за покупку."""
    # Фиксированное значение — 1 балл за 1 рубль
    bonus_rate = 1
    points = int(amount_paid * bonus_rate)
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users SET bonus_points = bonus_points + ?, updated_at = datetime('now')
            WHERE id = ?
        """, (points, user_id))
        conn.commit()
        return points
    except:
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


# ============================================
# ADMIN — ТРАНСПОРТ (ПОЕЗДА И МАРШРУТЫ)
# ============================================

def get_all_trips_with_details(limit=100):
    """Получить все рейсы с информацией о вагонах и местах."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                t.id as trip_id,
                t.departure_datetime,
                t.arrival_datetime,
                t.status,
                t.service_fee,
                t.price_sitting,
                t.price_reserved_seat,
                t.price_compartment,
                t.price_luxury,
                t.price_soft,
                t.price_sv,
                s_from.name as from_station,
                s_from.city as from_city,
                s_to.name as to_station,
                s_to.city as to_city,
                tr.number as train_number,
                tr.name as train_name,
                tr.type as train_type,
                tr.operator as train_operator,
                tr.id as train_id,
                r.distance_km,
                r.duration_minutes
            FROM trips t
            JOIN routes r ON t.route_id = r.id
            JOIN stations s_from ON r.departure_station_id = s_from.id
            JOIN stations s_to ON r.arrival_station_id = s_to.id
            JOIN trains tr ON t.train_id = tr.id
            ORDER BY t.departure_datetime DESC
            LIMIT ?
        """, (limit,))
        
        trips = []
        for row in cursor.fetchall():
            trip = dict(row)
            
            # Разделяем дату и время
            if trip['departure_datetime']:
                parts = trip['departure_datetime'].split(' ')
                trip['departure_date'] = parts[0] if len(parts) > 0 else ''
                trip['departure_time'] = parts[1][:5] if len(parts) > 1 else ''
            
            if trip['arrival_datetime']:
                parts = trip['arrival_datetime'].split(' ')
                trip['arrival_time'] = parts[1][:5] if len(parts) > 1 else ''
            
            # Получаем вагоны для этого рейса
            wagons = get_wagons_for_trip(cursor, trip['trip_id'], trip['train_id'], trip)
            
            total_seats = sum(w['total_seats'] for w in wagons)
            available_seats = sum(w['available_seats'] for w in wagons)
            
            # Находим минимальную цену
            min_price = None
            for w in wagons:
                if w['price'] > 0 and (min_price is None or w['price'] < min_price):
                    min_price = w['price']
            
            trip['wagons'] = wagons
            trip['total_seats'] = total_seats
            trip['available_seats'] = available_seats
            trip['min_price'] = min_price or 0
            
            trips.append(trip)
        
        return trips
        
    except Exception as e:
        print(f"Error in get_all_trips_with_details: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        cursor.close()
        conn.close()


def get_wagons_for_trip(cursor, trip_id, train_id, trip_prices):
    """Получить вагоны и места для конкретного рейса."""
    try:
        cursor.execute("""
            SELECT 
                w.id as wagon_id,
                w.number as wagon_number,
                w.type as wagon_type,
                w.class as wagon_class,
                w.total_seats,
                COUNT(ts.id) as total_trip_seats,
                SUM(CASE WHEN ts.is_available = 1 THEN 1 ELSE 0 END) as available_seats
            FROM wagons w
            JOIN seats s ON s.wagon_id = w.id
            JOIN trip_seats ts ON ts.seat_id = s.id AND ts.trip_id = ?
            WHERE w.train_id = ?
            GROUP BY w.id
            ORDER BY w.number
        """, (trip_id, train_id))
        
        wagons = []
        for w_row in cursor.fetchall():
            wagon = dict(w_row)
            
            # Определяем цену для типа вагона
            price = 0
            wagon_type = (wagon.get('wagon_type') or '').lower()
            
            if wagon_type == 'sitting':
                price = trip_prices.get('price_sitting', 0) or 0
            elif wagon_type == 'reserved_seat' or wagon_type == 'reserved':
                price = trip_prices.get('price_reserved_seat', 0) or 0
            elif wagon_type == 'compartment' or wagon_type == 'coupe':
                price = trip_prices.get('price_compartment', 0) or 0
            elif wagon_type == 'luxury' or wagon_type == 'lux':
                price = trip_prices.get('price_luxury', 0) or 0
            elif wagon_type == 'sv':
                price = trip_prices.get('price_sv', 0) or 0
            elif wagon_type == 'soft':
                price = trip_prices.get('price_soft', 0) or 0
            
            wagons.append({
                'number': wagon.get('wagon_number', '—'),
                'type': wagon.get('wagon_type', '—'),
                'class': wagon.get('wagon_class', '—'),
                'total_seats': wagon.get('total_seats', 0) or 0,
                'available_seats': wagon.get('available_seats', 0) or 0,
                'price': price
            })
        
        return wagons
        
    except Exception as e:
        print(f"Error in get_wagons_for_trip: {e}")
        return []