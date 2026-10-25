# Art Studio Website

A small full-stack website for an art studio. Customers can **buy paintings**, **book a wall painting date**, and **request custom pottery**. The studio (admin) adds paintings and confirms / declines bookings and pottery requests.

**Tech stack:** Python + Flask (backend), SQLite (database), plain HTML/CSS/JavaScript (frontend).

## Painting images
The painting pictures come from `seedData.zip`. Copy all the image files (`p-001.jpg` to `p-012.jpg`) into the **`static/images/`** folder, keeping the same file names as in `seed.json`. If an image is missing, the site shows an "Image coming soon" box instead.

## What you need
- Python 3.9 or newer (check with `python --version`)

## How to run (clean machine)

```bash
# 1. get the code
git clone <your-repo-url>
cd <your-repo-folder>

# 2. create a virtual environment and install Flask
python -m venv venv
# Windows:      venv\Scripts\activate
# Mac / Linux:  source venv/bin/activate
pip install -r requirements.txt

# 3. create your settings file
# Windows:      copy .env.example .env
# Mac / Linux:  cp .env.example .env
# (open .env and change SECRET_KEY)

# 4. create the database and add the starting data
python seed.py

# 5. start the app
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

## Logging in
- **Customer:** click "Create an account" on the login page.
- **Studio (admin):** log in with the studio account from `seed.json` (`studio@artstudio.in` / `Studio@123`). It is created by `python seed.py`. Studio sign-up is not part of the app.

## Run the tests
```bash
python -m unittest discover tests -v
```

## Project files
| File | What it does |
| --- | --- |
| `app.py` | All the backend routes (login, paintings, orders, bookings, pottery) |
| `db.py`, `schema.sql` | Database connection and table definitions |
| `seed.py`, `seed.json` | Reads the seed data (paintings, pottery items, glazes, wall rate, studio login) into the database |
| `config.py` | Reads settings from `.env` |
| `static/` | The web pages (HTML), `app.js` (shared helpers), `style.css` and `images/` (painting pictures) |
| `tests/test_app.py` | Tests for the main rules |
| `DESIGN.md` | Design answers: roles, database, double-booking, what is done |

## Main rules (all checked on the server)
- A painting can be bought only once; cancelling the order makes it available again.
- Wall booking: date 7-90 days away, size 10-500 sq ft, one booking per date, price = size x rate, customer can cancel until 3 days before.
- Pottery: quantity 1-12, needed-by at least 14 days away, edit/cancel only while "requested".
- Not logged in = 401, wrong role = 403, someone else's record = 404.
