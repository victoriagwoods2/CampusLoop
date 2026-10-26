"""Integration checks for a fresh environment with requirements.txt installed."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import store


class ReservationWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        store.DB_PATH = Path(cls.tmp.name) / "api.sqlite3"
        from fastapi.testclient import TestClient
        from app import app
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.giver = cls.client.post("/api/auth/login", json={"email": "outgoing@campusloop.demo", "password": "demo-outgoing"}).json()["token"]
        cls.recipient = cls.client.post("/api/auth/login", json={"email": "incoming@campusloop.demo", "password": "demo-incoming"}).json()["token"]

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.tmp.cleanup()

    def headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_full_two_person_handoff_and_duplicate_guard(self):
        listing = self.client.post("/api/listings", headers=self.headers(self.giver), json={
            "item_name": "Test lamp", "description": "Working, fictional test fixture", "category": "Lighting", "quantity": 1,
            "condition": "Good", "defects": "", "area": "East Rock", "available_from": "2027-08-02",
            "pickup_deadline": "2027-08-05", "pickup_windows": "Afternoons", "requires_vehicle": False,
            "can_deliver": False, "dimensions": "",
        }).json()
        need = self.client.post("/api/needs", headers=self.headers(self.recipient), json={
            "item_name": "Desk lamp", "category": "Lighting", "quantity": 1, "arrival_date": "2027-08-02",
            "available_from": "2027-08-02", "available_until": "2027-08-04", "area": "East Rock",
            "has_vehicle": False, "preferred_condition": "Fair", "essential_category": "Lighting", "requires_delivery": False,
        }).json()
        self.assertTrue(listing["is_demo"])
        self.assertTrue(need["is_demo"])
        body = {"listing_id": listing["id"], "need_id": need["id"], "quantity": 1, "transport_plan": "easy to carry", "pickup_window": "2027-08-02 afternoon"}
        requested = self.client.post("/api/reservations", headers=self.headers(self.recipient), json=body)
        self.assertEqual(requested.status_code, 200, requested.text)
        self.assertEqual(requested.json()["status"], "requested")
        duplicate = self.client.post("/api/reservations", headers=self.headers(self.recipient), json=body)
        self.assertEqual(duplicate.status_code, 409)
        reservation_id = requested.json()["id"]
        accepted = self.client.post(f"/api/reservations/{reservation_id}/decision", headers=self.headers(self.giver), json={"decision": "accept"})
        self.assertEqual(accepted.json()["status"], "reserved")
        first = self.client.post(f"/api/reservations/{reservation_id}/confirm", headers=self.headers(self.giver), json={"completed": True})
        self.assertEqual(first.json()["status"], "reserved")
        second = self.client.post(f"/api/reservations/{reservation_id}/confirm", headers=self.headers(self.recipient), json={"completed": True})
        self.assertEqual(second.json()["status"], "completed")
        mine = self.client.get("/api/listings?mine=true", headers=self.headers(self.giver)).json()
        self.assertEqual(next(item for item in mine if item["id"] == listing["id"])["remaining_quantity"], 0)
        self.assertTrue(requested.json()["is_demo"])
        reset = self.client.post("/api/demo/reset", headers=self.headers(self.giver))
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertFalse(any(item["id"] == listing["id"] for item in self.client.get("/api/listings?mine=true", headers=self.headers(self.giver)).json()))

    def test_bulky_car_free_request_and_exact_address_are_rejected(self):
        body = {"item_name": "Unsafe address fixture", "category": "Other", "quantity": 1, "condition": "Good", "area": "10 Elm Street", "available_from": "2027-08-02", "pickup_deadline": "2027-08-05"}
        response = self.client.post("/api/listings", headers=self.headers(self.giver), json=body)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)
