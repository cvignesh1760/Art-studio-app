# DESIGN.md

## How do login and the two roles work?
Customers sign up on the register page (name, email, password). Passwords are stored as hashes (Werkzeug), never as plain text. After login the server saves the user id in a signed session cookie. The studio (admin) account comes from `seed.json` and is created by `seed.py`, because studio sign-up is out of scope.

Every API route in `app.py` has a `@login_required(...)` check that runs on the **server**, not just in the browser:
- not logged in -> **401**
- wrong role (for example a customer adding a painting, or the admin buying one) -> **403**
- a customer asking for another customer's order/booking/request -> **404** (the query only looks at the customer's own rows, so it looks like it does not exist)

Customers only ever see their own records; the admin sees all of them.

## Which database did you choose, and why?
**SQLite.** It is a single file, needs no account or server, and works on a clean machine with just Python (the `sqlite3` module comes with Python). That makes it easy for anyone to run the project. The data is small and relational (users, paintings, orders, bookings, pottery requests), which SQLite handles well. Moving to a cloud database later would mostly mean changing `db.py` and some SQL.

## How do you stop two people from taking the same painting or date?
I let the database decide, so it is safe even if two people click at the same moment:
- **Painting:** buying runs `UPDATE paintings SET status='sold' WHERE id=? AND status='available'`. Only one request can change the row. The other sees `rowcount = 0` and gets a "just sold" message (409). A unique index on `orders(painting_id)` for active orders is a second safety net.
- **Wall date:** a unique index on `bookings(booking_date)` that only covers `requested` and `confirmed` bookings. A second booking on the same date raises an error, which becomes a "date just taken" message (409). A declined or cancelled booking frees the date again.
- Status changes (confirm, decline, cancel, accept) also use `WHERE status = '...'` so a record cannot be changed twice by mistake.

## What did you finish, what did you leave out, and what would you do next?
**Finished**
- Sign up, login, logout, two roles with server-side checks (401 / 403 / 404)
- Paintings: admin adds and edits (only while available), customers browse and buy, cancel order frees the painting
- Wall bookings: all validations, price = wall size x rate, admin confirms/declines, customer cancels until 3 days before
- Pottery requests: all validations, admin accepts/declines, customer edits/cancels only while "requested"
- Every list screen shows loading, empty and error states; refusals show clear messages
- Painting images, filter buttons (All / Available / Sold), a click-to-enlarge view, and a responsive layout that works on phones
- Automated tests for the main rules (`tests/test_app.py`)

**Left out (out of scope in the brief)**
Real payments, password reset, email verification, social login, reviews, coupons, delivery tracking, emails/SMS, image uploads, fancy styling, mobile layout, deployment.

**Other notes**
- All starting data (paintings, pottery items, glazes, wall rate of ₹150/sq ft, studio login) is loaded from `seed.json`, the seed file from the brief. Painting images are loaded from `static/images/` using the `imageUrl` paths in the seed; uploading new images from the website is out of scope.
- Painting prices are shown in rupees (₹).

**Next steps**
- Pagination for long lists
- A cloud-hosted database (for example PostgreSQL)
- Show the studio a calendar of booked dates
- CSRF protection for the forms
- Move the frontend to a framework if the app grows
