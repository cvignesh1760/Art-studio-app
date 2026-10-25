"""Art Studio website - backend (Flask + SQLite).

Everything lives in this one file so it is easy to read top to bottom:
  1. setup and helpers
  2. login / register
  3. paintings and orders
  4. wall painting bookings
  5. pottery requests
"""
import math
import sqlite3
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request, session

import config
from db import close_db, get_db, init_db
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["DATABASE"] = config.DATABASE_PATH
app.teardown_appcontext(close_db)

with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# 1. Helpers
# ---------------------------------------------------------------------------
def error(message, status):
    return jsonify({"error": message}), status


def today():
    """Today's date in India (IST = UTC + 5:30)."""
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()


def parse_date(text):
    try:
        return datetime.strptime(str(text), "%Y-%m-%d").date()
    except ValueError:
        return None


def to_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def to_whole_number(value):
    number = to_number(value)
    if number is None or number != int(number):
        return None
    return int(number)


def current_user():
    """Returns the logged-in user (as a row) or None."""
    if "user" not in g:
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            g.user = get_db().execute(
                "SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
    return g.user


def login_required(role=None):
    """Checks the role on the SERVER for every request.
    Not logged in -> 401, wrong role -> 403."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return error("Please log in first.", 401)
            if role is not None and user["role"] != role:
                return error("You are not allowed to do this.", 403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def user_to_dict(user):
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


def get_wall_rate():
    row = get_db().execute("SELECT value FROM settings WHERE key = 'wall_rate'").fetchone()
    return float(row["value"]) if row else 0.0


def get_own_row(table, row_id):
    """Customers only get their OWN records. Someone else's record -> None (so 404).
    Admins can see every record."""
    user = current_user()
    db = get_db()
    if user["role"] == "admin":
        return db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    return db.execute(
        f"SELECT * FROM {table} WHERE id = ? AND user_id = ?", (row_id, user["id"])
    ).fetchone()


# ---------------------------------------------------------------------------
# 2. Login / register
# ---------------------------------------------------------------------------
@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name:
        return error("Please enter your name.", 400)
    if "@" not in email:
        return error("Please enter a valid email.", 400)
    if len(password) < 6:
        return error("Password must be at least 6 characters.", 400)

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'customer')",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return error("That email is already registered.", 409)

    session.clear()
    session["user_id"] = cur.lastrowid
    return jsonify({"id": cur.lastrowid, "name": name, "email": email, "role": "customer"}), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("Wrong email or password.", 401)

    session.clear()
    session["user_id"] = user["id"]
    return jsonify(user_to_dict(user))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.get("/api/me")
@login_required()
def me():
    return jsonify(user_to_dict(current_user()))


@app.get("/api/config")
@login_required()
def get_config():
    """Info the forms need: wall rate, pottery items and glazes."""
    db = get_db()
    return jsonify(
        {
            "wall_rate": get_wall_rate(),
            "items": [dict(r) for r in db.execute("SELECT id, name FROM pottery_items ORDER BY name")],
            "glazes": [dict(r) for r in db.execute("SELECT id, name FROM glazes ORDER BY name")],
        }
    )


@app.get("/")
def home():
    return app.send_static_file("index.html")


# ---------------------------------------------------------------------------
# 3. Paintings and orders
# ---------------------------------------------------------------------------
def read_painting_form(data):
    """Checks title/description/price. Returns (values, error_message)."""
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    price = to_number(data.get("price"))
    if not title:
        return None, "Please enter a title."
    if price is None or price <= 0:
        return None, "Price must be a number greater than 0."
    return (title, description, price), None


@app.get("/api/paintings")
@login_required()
def list_paintings():
    rows = get_db().execute(
        "SELECT * FROM paintings ORDER BY status ASC, id DESC"  # 'available' sorts first
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/paintings")
@login_required("admin")
def add_painting():
    values, problem = read_painting_form(request.get_json(silent=True) or {})
    if problem:
        return error(problem, 400)
    db = get_db()
    cur = db.execute(
        "INSERT INTO paintings (title, description, price) VALUES (?, ?, ?)", values
    )
    db.commit()
    painting = db.execute("SELECT * FROM paintings WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(painting)), 201


@app.put("/api/paintings/<int:painting_id>")
@login_required("admin")
def edit_painting(painting_id):
    db = get_db()
    painting = db.execute("SELECT * FROM paintings WHERE id = ?", (painting_id,)).fetchone()
    if painting is None:
        return error("Painting not found.", 404)

    values, problem = read_painting_form(request.get_json(silent=True) or {})
    if problem:
        return error(problem, 400)

    # Only edit while still available (the WHERE makes this check safe)
    cur = db.execute(
        "UPDATE paintings SET title = ?, description = ?, price = ? "
        "WHERE id = ? AND status = 'available'",
        values + (painting_id,),
    )
    db.commit()
    if cur.rowcount == 0:
        return error("This painting is already sold and can no longer be edited.", 409)
    return jsonify(dict(db.execute("SELECT * FROM paintings WHERE id = ?", (painting_id,)).fetchone()))


@app.post("/api/orders")
@login_required("customer")
def buy_painting():
    data = request.get_json(silent=True) or {}
    painting_id = to_whole_number(data.get("painting_id"))
    if painting_id is None:
        return error("Please choose a painting.", 400)

    db = get_db()
    if db.execute("SELECT id FROM paintings WHERE id = ?", (painting_id,)).fetchone() is None:
        return error("Painting not found.", 404)

    # THE IMPORTANT PART: this single UPDATE only works if the painting is still
    # 'available'. If two people click Buy at the same time, only one UPDATE changes
    # a row (rowcount = 1). The other one gets rowcount = 0 and is refused.
    cur = db.execute(
        "UPDATE paintings SET status = 'sold' WHERE id = ? AND status = 'available'",
        (painting_id,),
    )
    if cur.rowcount == 0:
        db.rollback()
        return error("Sorry, this painting was just sold.", 409)

    try:
        db.execute(
            "INSERT INTO orders (user_id, painting_id) VALUES (?, ?)",
            (current_user()["id"], painting_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return error("Sorry, this painting was just sold.", 409)
    return jsonify({"message": "Order placed!"}), 201


@app.get("/api/orders")
@login_required()
def list_orders():
    user = current_user()
    sql = (
        "SELECT o.id, o.status, o.created_at, o.painting_id, p.title, p.price, p.image_url, u.name AS customer "
        "FROM orders o JOIN paintings p ON p.id = o.painting_id JOIN users u ON u.id = o.user_id "
    )
    if user["role"] == "admin":
        rows = get_db().execute(sql + "ORDER BY o.id DESC").fetchall()
    else:
        rows = get_db().execute(sql + "WHERE o.user_id = ? ORDER BY o.id DESC", (user["id"],)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/orders/<int:order_id>/cancel")
@login_required("customer")
def cancel_order(order_id):
    db = get_db()
    order = get_own_row("orders", order_id)
    if order is None:
        return error("Order not found.", 404)

    cur = db.execute(
        "UPDATE orders SET status = 'cancelled' WHERE id = ? AND status = 'placed'", (order_id,)
    )
    if cur.rowcount == 0:
        db.rollback()
        return error("This order is already cancelled.", 409)
    # the painting can be bought again
    db.execute("UPDATE paintings SET status = 'available' WHERE id = ?", (order["painting_id"],))
    db.commit()
    return jsonify({"message": "Order cancelled. The painting is available again."})


# ---------------------------------------------------------------------------
# 4. Wall painting bookings
# ---------------------------------------------------------------------------
BOOKING_SELECT = (
    "SELECT b.*, u.name AS customer FROM bookings b JOIN users u ON u.id = b.user_id "
)


@app.post("/api/bookings")
@login_required("customer")
def create_booking():
    data = request.get_json(silent=True) or {}
    booking_date = parse_date(data.get("date"))
    wall_size = to_number(data.get("wall_size"))
    address = str(data.get("address", "")).strip()

    if booking_date is None:
        return error("Please pick a valid date.", 400)
    days_away = (booking_date - today()).days
    if days_away < 7 or days_away > 90:
        return error("The date must be between 7 and 90 days from today.", 400)
    if wall_size is None or wall_size < 10 or wall_size > 500:
        return error("Wall size must be between 10 and 500 sq ft.", 400)
    if not address or len(address) > 300:
        return error("Please enter the address (up to 300 characters).", 400)

    price = round(wall_size * get_wall_rate(), 2)
    db = get_db()
    try:
        # The UNIQUE index in schema.sql refuses a second active booking on the same date.
        cur = db.execute(
            "INSERT INTO bookings (user_id, booking_date, wall_size, address, price) "
            "VALUES (?, ?, ?, ?, ?)",
            (current_user()["id"], booking_date.isoformat(), wall_size, address, price),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return error("Sorry, that date was just taken. Please pick another date.", 409)
    return jsonify({"id": cur.lastrowid, "price": price, "message": "Booking requested!"}), 201


@app.get("/api/bookings")
@login_required()
def list_bookings():
    user = current_user()
    if user["role"] == "admin":
        rows = get_db().execute(BOOKING_SELECT + "ORDER BY b.id DESC").fetchall()
    else:
        rows = get_db().execute(
            BOOKING_SELECT + "WHERE b.user_id = ? ORDER BY b.id DESC", (user["id"],)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/bookings/<int:booking_id>/cancel")
@login_required("customer")
def cancel_booking(booking_id):
    db = get_db()
    booking = get_own_row("bookings", booking_id)
    if booking is None:
        return error("Booking not found.", 404)
    if booking["status"] not in ("requested", "confirmed"):
        return error(f"A {booking['status']} booking cannot be cancelled.", 409)

    days_left = (parse_date(booking["booking_date"]) - today()).days
    if days_left < 3:
        return error("Too late: bookings can only be cancelled until 3 days before the date.", 409)

    cur = db.execute(
        "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status IN ('requested', 'confirmed')",
        (booking_id,),
    )
    db.commit()
    if cur.rowcount == 0:
        return error("This booking can no longer be cancelled.", 409)
    return jsonify({"message": "Booking cancelled."})


def studio_decides_booking(booking_id, new_status):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if booking is None:
        return error("Booking not found.", 404)
    cur = db.execute(
        "UPDATE bookings SET status = ? WHERE id = ? AND status = 'requested'",
        (new_status, booking_id),
    )
    db.commit()
    if cur.rowcount == 0:
        return error("Only a requested booking can be confirmed or declined.", 409)
    return jsonify({"message": f"Booking {new_status}."})


@app.post("/api/bookings/<int:booking_id>/confirm")
@login_required("admin")
def confirm_booking(booking_id):
    return studio_decides_booking(booking_id, "confirmed")


@app.post("/api/bookings/<int:booking_id>/decline")
@login_required("admin")
def decline_booking(booking_id):
    return studio_decides_booking(booking_id, "declined")


# ---------------------------------------------------------------------------
# 5. Pottery requests
# ---------------------------------------------------------------------------
POTTERY_SELECT = (
    "SELECT r.*, i.name AS item, g.name AS glaze, u.name AS customer "
    "FROM pottery_requests r "
    "JOIN pottery_items i ON i.id = r.item_id "
    "JOIN glazes g ON g.id = r.glaze_id "
    "JOIN users u ON u.id = r.user_id "
)


def read_pottery_form(data):
    """Checks the pottery form. Returns (values, error_message)."""
    db = get_db()
    item_id = to_whole_number(data.get("item_id"))
    glaze_id = to_whole_number(data.get("glaze_id"))
    quantity = to_whole_number(data.get("quantity"))
    needed_by = parse_date(data.get("needed_by"))

    if item_id is None or db.execute("SELECT 1 FROM pottery_items WHERE id = ?", (item_id,)).fetchone() is None:
        return None, "Please choose an item from the list."
    if glaze_id is None or db.execute("SELECT 1 FROM glazes WHERE id = ?", (glaze_id,)).fetchone() is None:
        return None, "Please choose a glaze from the list."
    if quantity is None or quantity < 1 or quantity > 12:
        return None, "Quantity must be between 1 and 12."
    if needed_by is None:
        return None, "Please pick a valid needed-by date."
    if (needed_by - today()).days < 14:
        return None, "The needed-by date must be at least 14 days from today."
    return (item_id, glaze_id, quantity, needed_by.isoformat()), None


@app.post("/api/pottery-requests")
@login_required("customer")
def create_pottery_request():
    values, problem = read_pottery_form(request.get_json(silent=True) or {})
    if problem:
        return error(problem, 400)
    db = get_db()
    cur = db.execute(
        "INSERT INTO pottery_requests (user_id, item_id, glaze_id, quantity, needed_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (current_user()["id"],) + values,
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "message": "Pottery request sent!"}), 201


@app.get("/api/pottery-requests")
@login_required()
def list_pottery_requests():
    user = current_user()
    if user["role"] == "admin":
        rows = get_db().execute(POTTERY_SELECT + "ORDER BY r.id DESC").fetchall()
    else:
        rows = get_db().execute(
            POTTERY_SELECT + "WHERE r.user_id = ? ORDER BY r.id DESC", (user["id"],)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/pottery-requests/<int:request_id>")
@login_required()
def get_pottery_request(request_id):
    if get_own_row("pottery_requests", request_id) is None:
        return error("Pottery request not found.", 404)
    row = get_db().execute(POTTERY_SELECT + "WHERE r.id = ?", (request_id,)).fetchone()
    return jsonify(dict(row))


@app.put("/api/pottery-requests/<int:request_id>")
@login_required("customer")
def edit_pottery_request(request_id):
    if get_own_row("pottery_requests", request_id) is None:
        return error("Pottery request not found.", 404)
    values, problem = read_pottery_form(request.get_json(silent=True) or {})
    if problem:
        return error(problem, 400)

    db = get_db()
    cur = db.execute(
        "UPDATE pottery_requests SET item_id = ?, glaze_id = ?, quantity = ?, needed_by = ? "
        "WHERE id = ? AND status = 'requested'",
        values + (request_id,),
    )
    db.commit()
    if cur.rowcount == 0:
        return error("Only a request that is still 'requested' can be edited.", 409)
    return jsonify({"message": "Pottery request updated."})


@app.post("/api/pottery-requests/<int:request_id>/cancel")
@login_required("customer")
def cancel_pottery_request(request_id):
    if get_own_row("pottery_requests", request_id) is None:
        return error("Pottery request not found.", 404)
    db = get_db()
    cur = db.execute(
        "UPDATE pottery_requests SET status = 'cancelled' WHERE id = ? AND status = 'requested'",
        (request_id,),
    )
    db.commit()
    if cur.rowcount == 0:
        return error("Only a request that is still 'requested' can be cancelled.", 409)
    return jsonify({"message": "Pottery request cancelled."})


def studio_decides_pottery(request_id, new_status):
    db = get_db()
    if db.execute("SELECT 1 FROM pottery_requests WHERE id = ?", (request_id,)).fetchone() is None:
        return error("Pottery request not found.", 404)
    cur = db.execute(
        "UPDATE pottery_requests SET status = ? WHERE id = ? AND status = 'requested'",
        (new_status, request_id),
    )
    db.commit()
    if cur.rowcount == 0:
        return error("Only a requested pottery request can be accepted or declined.", 409)
    return jsonify({"message": f"Pottery request {new_status}."})


@app.post("/api/pottery-requests/<int:request_id>/accept")
@login_required("admin")
def accept_pottery_request(request_id):
    return studio_decides_pottery(request_id, "accepted")


@app.post("/api/pottery-requests/<int:request_id>/decline")
@login_required("admin")
def decline_pottery_request(request_id):
    return studio_decides_pottery(request_id, "declined")


if __name__ == "__main__":
    app.run(debug=True)
