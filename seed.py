"""Fills the database with starting data from seed.json. Run it once:  python seed.py

seed.json is the seed data from the brief (paintings, pottery items, glazes,
wall rate and the studio login). It is safe to run this file more than once.
"""
import json
import os
import sqlite3

import config
from werkzeug.security import generate_password_hash

SEED_FILE = os.path.join(config.BASE_DIR, "seed.json")


def load_seed():
    with open(SEED_FILE, encoding="utf-8") as f:
        return json.load(f)


def seed_database(db_path=None):
    data = load_seed()
    db = sqlite3.connect(db_path or config.DATABASE_PATH)

    with open(os.path.join(config.BASE_DIR, "schema.sql")) as f:
        db.executescript(f.read())

    # The studio (admin) account. Studio sign-up is out of scope, so it is created here.
    studio = data["studioAccount"]
    db.execute(
        "INSERT OR IGNORE INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
        ("Studio", studio["email"].lower(), generate_password_hash(studio["password"])),
    )

    db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('wall_rate', ?)",
        (str(data["mural"]["ratePerSqFt"]),),
    )
    for item in data["potteryItems"]:
        db.execute("INSERT OR IGNORE INTO pottery_items (name) VALUES (?)", (item["name"],))
    for glaze in data["glazes"]:
        db.execute("INSERT OR IGNORE INTO glazes (name) VALUES (?)", (glaze["name"],))

    # only add the paintings if there are none yet (so re-running does not duplicate them)
    if db.execute("SELECT COUNT(*) FROM paintings").fetchone()[0] == 0:
        for p in data["paintings"]:
            db.execute(
                "INSERT INTO paintings (title, artist, image_url, description, price, status) VALUES (?, ?, ?, ?, ?, ?)",
                (p["title"], p.get("artist", ""), p.get("imageUrl", ""), p["description"], p["price"], p["status"]),
            )

    db.commit()
    db.close()


if __name__ == "__main__":
    seed_database()
    studio = load_seed()["studioAccount"]
    print("Database seeded.")
    print(f"Studio login: {studio['email']}  /  {studio['password']}")
