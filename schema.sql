-- All tables for the art studio app.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('customer', 'admin'))
);

-- Simple key/value settings (for example the wall painting rate)
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Seed data lists for pottery
CREATE TABLE IF NOT EXISTS pottery_items (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS glazes (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- 1. Paintings
CREATE TABLE IF NOT EXISTS paintings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    artist      TEXT NOT NULL DEFAULT '',
    image_url   TEXT NOT NULL DEFAULT '',   -- for example images/p-001.jpg (file lives in static/images)
    description TEXT NOT NULL DEFAULT '',
    price       REAL NOT NULL CHECK (price > 0),
    status      TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'sold'))
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    painting_id INTEGER NOT NULL REFERENCES paintings(id),
    status      TEXT NOT NULL DEFAULT 'placed' CHECK (status IN ('placed', 'cancelled')),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Safety net: a painting can have only ONE active order at a time.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_order_per_painting
    ON orders(painting_id) WHERE status = 'placed';

-- 2. Wall painting bookings
CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    booking_date TEXT NOT NULL,          -- format YYYY-MM-DD
    wall_size    REAL NOT NULL,          -- square feet
    address      TEXT NOT NULL,
    price        REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'requested'
                 CHECK (status IN ('requested', 'confirmed', 'declined', 'cancelled')),
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Safety net: a date can be held by only ONE active booking.
-- (declined / cancelled bookings free the date again)
CREATE UNIQUE INDEX IF NOT EXISTS one_active_booking_per_date
    ON bookings(booking_date) WHERE status IN ('requested', 'confirmed');

-- 3. Custom pottery requests
CREATE TABLE IF NOT EXISTS pottery_requests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    item_id    INTEGER NOT NULL REFERENCES pottery_items(id),
    glaze_id   INTEGER NOT NULL REFERENCES glazes(id),
    quantity   INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 12),
    needed_by  TEXT NOT NULL,            -- format YYYY-MM-DD
    status     TEXT NOT NULL DEFAULT 'requested'
               CHECK (status IN ('requested', 'accepted', 'declined', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
