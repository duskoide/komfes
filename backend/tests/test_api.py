from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # keeps the deterministic stdlib suite runnable without API extras
    TestClient = None

from hargaturun.api import create_app
from hargaturun.model_client import ModelUnavailable


class FakeModel:
    def parse(self, free_text: str) -> dict:
        return {
            "task": "parse",
            "parsed_input": {
                "item_name": "Roti Tawar",
                "category": "Bakery",
                "original_price": 20000,
                "cost": 10000,
                "stock": 30,
                "days_remaining": 1,
                "daily_sales": None,
                "total_shelf_life": 4,
                "shop_name": "Toko Sari",
            },
            "missing_fields": ["daily_sales"],
            "needs_confirmation": True,
        }

    def write(self, normalized_input: dict, engine_result: dict) -> dict:
        return {
            "task": "write",
            "explanation": "Stok barang lebih banyak dari perkiraan penjualan. Diskon membantu mengurangi potensi sisa.",
            "promo_copy": "Harga spesial untuk stok terbatas hari ini.",
        }


class DownModel(FakeModel):
    def write(self, normalized_input: dict, engine_result: dict) -> dict:
        raise ModelUnavailable


@unittest.skipIf(TestClient is None, "FastAPI test dependencies not installed")
class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.client_context = TestClient(create_app(database_path=self.db_path, model=FakeModel()))
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.tmp.cleanup()

    def recommendation_payload(self) -> dict:
        return {
            "item_name": "Roti Tawar",
            "category": "Bakery",
            "original_price": 20000,
            "cost": 10000,
            "stock": 30,
            "days_remaining": 1,
            "daily_sales": 5,
            "total_shelf_life": 4,
            "shop_name": "Toko Sari",
        }

    def publish_payload(self, recommendation: dict) -> dict:
        normalized = recommendation["normalized_input"]
        numbers = recommendation["recommendation"]
        return {
            "item_name": normalized["item_name"],
            "shop_name": normalized["shop_name"],
            "category": normalized["category"],
            "original_price": normalized["original_price"],
            "cost": normalized["cost"],
            "deal_price": numbers["recommended_price"],
            "discount_percent": numbers["discount_percent"],
            "days_remaining": normalized["days_remaining"],
            "initial_stock": 1,
            "promo_copy": recommendation["promo_copy"],
        }

    def test_structured_recommendation_uses_oracle(self):
        response = self.client.post("/api/recommend", json=self.recommendation_payload())
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "recommendation")
        self.assertEqual(result["recommendation"]["discount_percent"], 45)
        self.assertEqual(result["recommendation"]["recommended_price"], 11000)
        self.assertTrue(result["explanation"])

    def test_names_drop_wrapping_quotes_before_writer_and_preview(self):
        payload = self.recommendation_payload()
        payload["item_name"] = "''Roti Tawar''"
        payload["shop_name"] = "“Toko Sari”"

        response = self.client.post("/api/recommend", json=payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["normalized_input"]["item_name"], "Roti Tawar")
        self.assertEqual(result["normalized_input"]["shop_name"], "Toko Sari")
        self.assertEqual(result["preview"]["item_name"], "Roti Tawar")
        self.assertEqual(result["preview"]["shop_name"], "Toko Sari")

    def test_quote_only_names_are_rejected_after_normalization(self):
        payload = self.recommendation_payload()
        payload["item_name"] = "''"
        payload["shop_name"] = '""'

        response = self.client.post("/api/recommend", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["status"], "needs_confirmation")
        self.assertIn("item_name", response.json()["missing_fields"])

    def test_free_text_requests_confirmation(self):
        response = self.client.post("/api/recommend", json={"free_text": "roti 30 pcs"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["status"], "needs_confirmation")
        self.assertEqual(response.json()["missing_fields"], ["daily_sales"])

    def test_numbers_survive_writer_outage(self):
        with TestClient(create_app(database_path=Path(self.tmp.name) / "down.db", model=DownModel())) as client:
            response = client.post("/api/recommend", json=self.recommendation_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommendation"]["recommended_price"], 11000)
        self.assertEqual(response.json()["promo_copy"], "")

    def test_marketplace_lifecycle_and_persistence(self):
        recommendation = self.client.post(
            "/api/recommend", json=self.recommendation_payload()
        ).json()
        published = self.client.post(
            "/api/deals", json=self.publish_payload(recommendation)
        )
        self.assertEqual(published.status_code, 201)
        deal_id = published.json()["id"]

        claim = self.client.post(f"/api/deals/{deal_id}/claims")
        self.assertEqual(claim.status_code, 201)
        code = claim.json()["code"]
        self.assertEqual(self.client.post(f"/api/deals/{deal_id}/claims").status_code, 409)

        redeemed = self.client.post(f"/api/claims/{code.lower()}/redeem")
        self.assertEqual(redeemed.status_code, 200)
        self.assertEqual(redeemed.json()["status"], "redeemed")
        self.assertEqual(self.client.post(f"/api/claims/{code}/redeem").status_code, 409)

        self.client_context.__exit__(None, None, None)
        with TestClient(create_app(database_path=self.db_path, model=FakeModel())) as restarted:
            deals = restarted.get("/api/deals?status=sold_out").json()
            claims = restarted.get(f"/api/deals/{deal_id}/claims").json()
        self.assertEqual(len(deals), 1)
        self.assertEqual(claims[0]["status"], "redeemed")
        self.client_context = _ClosedContext()

    def test_removed_deal_keeps_existing_claim_redeemable(self):
        recommendation = self.client.post(
            "/api/recommend", json=self.recommendation_payload()
        ).json()
        published = self.client.post(
            "/api/deals", json=self.publish_payload(recommendation)
        ).json()
        claim = self.client.post(f"/api/deals/{published['id']}/claims").json()

        self.assertEqual(self.client.delete(f"/api/deals/{published['id']}").status_code, 204)
        redeemed = self.client.post(f"/api/claims/{claim['code']}/redeem")
        self.assertEqual(redeemed.status_code, 200)
        self.assertEqual(redeemed.json()["status"], "redeemed")

    def test_publish_rejects_below_margin_floor(self):
        payload = {
            "item_name": "Roti",
            "shop_name": "Toko",
            "category": "Bakery",
            "original_price": 15000,
            "cost": 10000,
            "deal_price": 10000,
            "discount_percent": 33,
            "days_remaining": 1,
            "initial_stock": 3,
            "promo_copy": "Promo",
        }
        response = self.client.post("/api/deals", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Rp500", response.json()["detail"])

    def test_demo_auth_and_shop_profile(self):
        phone = "+628123456789"
        self.assertEqual(
            self.client.post("/api/auth/otp/request", json={"phone": phone}).status_code,
            204,
        )
        session = self.client.post(
            "/api/auth/otp/verify", json={"phone": phone, "otp": "123456"}
        ).json()
        self.assertTrue(session["is_new_vendor"])
        profile = {"shop_name": "Toko Sari", "business_type": "bakery", "short_address": "Depok"}
        saved = self.client.post(
            "/api/shops",
            json=profile,
            headers={"Authorization": f"Bearer {session['token']}"},
        )
        self.assertEqual(saved.status_code, 200)
        with self.client.app.state.database.connect() as connection:
            persisted = connection.execute(
                "SELECT shop_name FROM shops WHERE phone = ?", (phone,)
            ).fetchone()
        self.assertEqual(persisted["shop_name"], "Toko Sari")
        next_session = self.client.post(
            "/api/auth/otp/verify", json={"phone": phone, "otp": "123456"}
        ).json()
        self.assertFalse(next_session["is_new_vendor"])
        self.assertEqual(next_session["shop"], profile)


class _ClosedContext:
    def __exit__(self, *args):
        return None


if __name__ == "__main__":
    unittest.main()
