create database brt_db;

-- ============================================
-- Bahn Routing Tools - Database Schema
-- Optimized version: 14 tables
-- ============================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;


-- ============================================
-- 1. USERS
-- ============================================
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    middle_name VARCHAR(100),
    birth_date DATE,
    citizenship VARCHAR(100),
    document_type ENUM('passport_rf', 'foreign_passport', 'birth_certificate', 'other'),
    document_series VARCHAR(10),
    document_number VARCHAR(20),
    bonus_points INT DEFAULT 0,
    loyalty_level ENUM('none', 'bronze', 'silver', 'gold', 'platinum') DEFAULT 'none',
    language VARCHAR(5) DEFAULT 'ru',
    currency VARCHAR(3) DEFAULT 'RUB',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 2. STATIONS
-- ============================================
CREATE TABLE stations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(255),
    country VARCHAR(100),
    timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
    is_active BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 3. ROUTES
-- ============================================
CREATE TABLE routes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    departure_station_id BIGINT NOT NULL,
    arrival_station_id BIGINT NOT NULL,
    distance_km DECIMAL(8,1),
    duration_minutes INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (departure_station_id) REFERENCES stations(id) ON DELETE RESTRICT,
    FOREIGN KEY (arrival_station_id) REFERENCES stations(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. ROUTE STOPS
-- ============================================
CREATE TABLE route_stops (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    route_id BIGINT NOT NULL,
    station_id BIGINT NOT NULL,
    stop_order INT NOT NULL,
    arrival_offset INT COMMENT 'minutes from departure',
    departure_offset INT COMMENT 'minutes from departure',
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 5. TRAINS
-- ============================================
CREATE TABLE trains (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    number VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    type ENUM('high_speed', 'express', 'passenger', 'suburban') NOT NULL,
    operator VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 6. WAGONS
-- ============================================
CREATE TABLE wagons (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    train_id BIGINT NOT NULL,
    number VARCHAR(10) NOT NULL,
    type ENUM('sitting', 'reserved_seat', 'compartment', 'luxury', 'soft', 'sv') NOT NULL,
    class ENUM('economy', 'business', 'first') NOT NULL,
    total_seats INT NOT NULL,
    FOREIGN KEY (train_id) REFERENCES trains(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 7. SEATS
-- ============================================
CREATE TABLE seats (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    wagon_id BIGINT NOT NULL,
    number VARCHAR(5) NOT NULL,
    position ENUM('top', 'bottom', 'top_side', 'bottom_side', 'single'),
    has_table BOOLEAN DEFAULT FALSE,
    near_toilet BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (wagon_id) REFERENCES wagons(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 8. TRIPS
-- ============================================
CREATE TABLE trips (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    route_id BIGINT NOT NULL,
    train_id BIGINT NOT NULL,
    departure_datetime DATETIME NOT NULL,
    arrival_datetime DATETIME NOT NULL,
    base_price_economy DECIMAL(10,2),
    base_price_business DECIMAL(10,2),
    base_price_first DECIMAL(10,2),
    service_fee DECIMAL(10,2) DEFAULT 0,
    status ENUM('scheduled', 'boarding', 'en_route', 'arrived', 'cancelled', 'delayed') DEFAULT 'scheduled',
    delay_minutes INT DEFAULT 0,
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE RESTRICT,
    FOREIGN KEY (train_id) REFERENCES trains(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 9. TRIP SEATS (availability)
-- ============================================
CREATE TABLE trip_seats (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trip_id BIGINT NOT NULL,
    seat_id BIGINT NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
    FOREIGN KEY (seat_id) REFERENCES seats(id) ON DELETE RESTRICT,
    UNIQUE KEY unique_trip_seat (trip_id, seat_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 10. ORDERS
-- ============================================
CREATE TABLE orders (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(20) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL,
    status ENUM('pending', 'paid', 'partially_refunded', 'refunded', 'cancelled') DEFAULT 'pending',
    total_amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB',
    payment_method ENUM('card', 'sbp', 'sberpay', 'other'),
    promo_code VARCHAR(50),
    paid_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL COMMENT 'unpaid orders expire after 20 min',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 11. TICKETS
-- ============================================
CREATE TABLE tickets (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    trip_id BIGINT NOT NULL,
    seat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL COMMENT 'passenger',
    passenger_type ENUM('adult', 'child', 'infant') NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    status ENUM('active', 'used', 'refunded', 'cancelled') DEFAULT 'active',
    ticket_number VARCHAR(20) NOT NULL UNIQUE,
    refund_amount DECIMAL(10,2),
    refunded_at TIMESTAMP NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE RESTRICT,
    FOREIGN KEY (seat_id) REFERENCES seats(id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 12. TRANSACTIONS
-- ============================================
CREATE TABLE transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    type ENUM('payment', 'refund') NOT NULL,
    gateway VARCHAR(50),
    external_id VARCHAR(255),
    status ENUM('pending', 'success', 'failed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 13. SEARCH HISTORY
-- ============================================
CREATE TABLE search_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    from_station_id BIGINT NOT NULL,
    to_station_id BIGINT NOT NULL,
    departure_date DATE NOT NULL,
    passengers_json JSON COMMENT '{"adults": 1, "children": 0, "infants": 0}',
    class ENUM('economy', 'business', 'first'),
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (from_station_id) REFERENCES stations(id) ON DELETE RESTRICT,
    FOREIGN KEY (to_station_id) REFERENCES stations(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 14. SUBSCRIPTIONS
-- ============================================
CREATE TABLE subscriptions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unsubscribed_at TIMESTAMP NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX idx_routes_departure ON routes(departure_station_id);
CREATE INDEX idx_routes_arrival ON routes(arrival_station_id);
CREATE INDEX idx_route_stops_route ON route_stops(route_id);
CREATE INDEX idx_wagons_train ON wagons(train_id);
CREATE INDEX idx_seats_wagon ON seats(wagon_id);
CREATE INDEX idx_trips_route ON trips(route_id);
CREATE INDEX idx_trips_train ON trips(train_id);
CREATE INDEX idx_trips_departure ON trips(departure_datetime);
CREATE INDEX idx_trips_status ON trips(status);
CREATE INDEX idx_trip_seats_trip ON trip_seats(trip_id);
CREATE INDEX idx_trip_seats_available ON trip_seats(trip_id, is_available);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_tickets_order ON tickets(order_id);
CREATE INDEX idx_tickets_trip ON tickets(trip_id);
CREATE INDEX idx_tickets_user ON tickets(user_id);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_transactions_order ON transactions(order_id);
CREATE INDEX idx_search_history_user ON search_history(user_id);
CREATE INDEX idx_search_history_stations ON search_history(from_station_id, to_station_id);

SET FOREIGN_KEY_CHECKS = 1;