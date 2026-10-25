"""Basic tests. Run with:  python -m unittest discover tests -v"""
import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as studio  # noqa: E402
import config  # noqa: E402
from seed import load_seed, seed_database  # noqa: E402

SEED = load_seed()


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        seed_database(self.tmp.name)
        studio.app.config["DATABASE"] = self.tmp.name
        studio.app.config["TESTING"] = True
        self.anon = studio.app.test_client()
        self.alice = self.make_customer("alice@example.com")
        self.bob = self.make_customer("bob@example.com")
        self.admin = studio.app.test_client()
        self.admin.post("/api/login", json={"email": SEED["studioAccount"]["email"], "password": SEED["studioAccount"]["password"]})

    def tearDown(self):
        os.unlink(self.tmp.name)

    def make_customer(self, email):
        client = studio.app.test_client()
        client.post("/api/register", json={"name": email, "email": email, "password": "secret1"})
        return client

    def day(self, days_from_now):
        return (studio.today() + timedelta(days=days_from_now)).isoformat()

    # ---- roles ----
    def test_not_logged_in_is_401(self):
        self.assertEqual(self.anon.get("/api/paintings").status_code, 401)

    def test_customer_cannot_add_painting_403(self):
        r = self.alice.post("/api/paintings", json={"title": "x", "price": 10})
        self.assertEqual(r.status_code, 403)

    def test_admin_cannot_buy_403(self):
        self.assertEqual(self.admin.post("/api/orders", json={"painting_id": 1}).status_code, 403)

    # ---- paintings ----
    def test_painting_can_only_be_bought_once_and_cancel_frees_it(self):
        self.assertEqual(self.alice.post("/api/orders", json={"painting_id": 1}).status_code, 201)
        self.assertEqual(self.bob.post("/api/orders", json={"painting_id": 1}).status_code, 409)
        order_id = self.alice.get("/api/orders").get_json()[0]["id"]
        self.assertEqual(self.alice.post(f"/api/orders/{order_id}/cancel").status_code, 200)
        self.assertEqual(self.bob.post("/api/orders", json={"painting_id": 1}).status_code, 201)

    def test_other_customers_order_is_404(self):
        self.alice.post("/api/orders", json={"painting_id": 1})
        order_id = self.alice.get("/api/orders").get_json()[0]["id"]
        self.assertEqual(self.bob.post(f"/api/orders/{order_id}/cancel").status_code, 404)
        self.assertEqual(self.bob.get("/api/orders").get_json(), [])

    def test_sold_painting_cannot_be_edited(self):
        self.alice.post("/api/orders", json={"painting_id": 1})
        r = self.admin.put("/api/paintings/1", json={"title": "New", "price": 99})
        self.assertEqual(r.status_code, 409)

    # ---- bookings ----
    def book(self, client, days=10, size=100):
        return client.post("/api/bookings", json={"date": self.day(days), "wall_size": size, "address": "12 Main St"})

    def test_booking_price_and_double_booking(self):
        r = self.book(self.alice)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["price"], 100 * SEED["mural"]["ratePerSqFt"])
        self.assertEqual(self.book(self.bob).status_code, 409)

    def test_booking_rules(self):
        self.assertEqual(self.book(self.alice, days=6).status_code, 400)
        self.assertEqual(self.book(self.alice, days=91).status_code, 400)
        self.assertEqual(self.book(self.alice, size=9).status_code, 400)
        self.assertEqual(self.book(self.alice, size=501).status_code, 400)

    def test_declined_booking_frees_the_date(self):
        self.book(self.alice)
        booking_id = self.alice.get("/api/bookings").get_json()[0]["id"]
        self.assertEqual(self.admin.post(f"/api/bookings/{booking_id}/decline").status_code, 200)
        self.assertEqual(self.book(self.bob).status_code, 201)

    def test_cancel_booking_3_day_rule(self):
        self.book(self.alice, days=10)
        booking_id = self.alice.get("/api/bookings").get_json()[0]["id"]
        # move the booking to 2 days from now, then it is too late to cancel
        db = studio.sqlite3.connect(self.tmp.name)
        db.execute("UPDATE bookings SET booking_date = ?", (self.day(2),))
        db.commit()
        db.close()
        self.assertEqual(self.alice.post(f"/api/bookings/{booking_id}/cancel").status_code, 409)

    def test_customer_cannot_confirm_booking(self):
        self.book(self.alice)
        booking_id = self.alice.get("/api/bookings").get_json()[0]["id"]
        self.assertEqual(self.alice.post(f"/api/bookings/{booking_id}/confirm").status_code, 403)

    # ---- pottery ----
    def pottery(self, client, quantity=2, days=20):
        return client.post(
            "/api/pottery-requests",
            json={"item_id": 1, "glaze_id": 1, "quantity": quantity, "needed_by": self.day(days)},
        )

    def test_pottery_rules(self):
        self.assertEqual(self.pottery(self.alice).status_code, 201)
        self.assertEqual(self.pottery(self.alice, quantity=0).status_code, 400)
        self.assertEqual(self.pottery(self.alice, quantity=13).status_code, 400)
        self.assertEqual(self.pottery(self.alice, days=13).status_code, 400)

    def test_pottery_cannot_be_edited_after_accepted(self):
        self.pottery(self.alice)
        request_id = self.alice.get("/api/pottery-requests").get_json()[0]["id"]
        self.assertEqual(self.admin.post(f"/api/pottery-requests/{request_id}/accept").status_code, 200)
        form = {"item_id": 1, "glaze_id": 1, "quantity": 3, "needed_by": self.day(20)}
        self.assertEqual(self.alice.put(f"/api/pottery-requests/{request_id}", json=form).status_code, 409)
        self.assertEqual(self.alice.post(f"/api/pottery-requests/{request_id}/cancel").status_code, 409)

    def test_other_customers_pottery_is_404(self):
        self.pottery(self.alice)
        request_id = self.alice.get("/api/pottery-requests").get_json()[0]["id"]
        self.assertEqual(self.bob.get(f"/api/pottery-requests/{request_id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
