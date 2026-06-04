-- ============================================================
--  init_db.sql  –  Run this ONCE to create all dataset tables
--  that are used by raw SQL queries in the Flask app.
--
--  Usage:
--    psql -U postgres -d movie_booking_db -f init_db.sql
--
--  The app also auto-creates these on startup via _create_dataset_tables()
--  in app.py, so this file is only needed for manual / CI setup.
-- ============================================================

CREATE TABLE IF NOT EXISTS movies (
    movie_id     VARCHAR(20) PRIMARY KEY,
    title        VARCHAR(200) NOT NULL,
    genre        VARCHAR(100),
    language     VARCHAR(50),
    duration     INTEGER,
    rating       NUMERIC(3,1),
    release_date DATE,
    description  TEXT
);

CREATE TABLE IF NOT EXISTS theaters (
    theater_id VARCHAR(20) PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    city       VARCHAR(100),
    state      VARCHAR(100),
    location   TEXT
);

CREATE TABLE IF NOT EXISTS screens (
    screen_id     VARCHAR(20) PRIMARY KEY,
    theater_id    VARCHAR(20) REFERENCES theaters(theater_id) ON DELETE CASCADE,
    screen_number INTEGER,
    total_seats   INTEGER
);

CREATE TABLE IF NOT EXISTS shows (
    show_id          VARCHAR(20) PRIMARY KEY,
    movie_id         VARCHAR(20) REFERENCES movies(movie_id)   ON DELETE CASCADE,
    theater_id       VARCHAR(20) REFERENCES theaters(theater_id) ON DELETE CASCADE,
    screen_id        VARCHAR(20) REFERENCES screens(screen_id) ON DELETE CASCADE,
    show_date        DATE,
    start_time       VARCHAR(20),
    price_per_ticket NUMERIC(10,2),
    available_seats  INTEGER
);

CREATE TABLE IF NOT EXISTS users (
    user_id    VARCHAR(20) PRIMARY KEY,
    name       VARCHAR(200),
    email      VARCHAR(150),
    city       VARCHAR(100),
    phone      VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id   SERIAL PRIMARY KEY,
    movie_id    VARCHAR(20) REFERENCES movies(movie_id) ON DELETE CASCADE,
    user_id     VARCHAR(20) REFERENCES users(user_id)   ON DELETE CASCADE,
    rating      NUMERIC(3,1),
    review_text TEXT,
    review_date DATE DEFAULT CURRENT_DATE
);

-- ── Sample screens (run after inserting theatres) ────────────────────────────
-- Uncomment and adjust theater_id values to match your theatre IDs
-- INSERT INTO screens (screen_id, theater_id, screen_number, total_seats) VALUES
--   ('SC000001', 'T123456', 1, 150),
--   ('SC000002', 'T123456', 2, 200),
--   ('SC000003', 'T123456', 3, 100);
