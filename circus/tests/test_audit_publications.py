"""Purely local tests for the Circus read-only publication audit."""
import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("circus_audit", ROOT / "circus/audit_publications.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
DAY = dt.date(2026, 10, 22)


def row(media_id, kind, caption, clock="19:00:00"):
    return {"id": media_id, "timestamp": f"2026-10-22T{clock}-05:00",
            "media_type": "VIDEO" if kind == "REELS" else "IMAGE",
            "media_product_type": kind, "caption": caption,
            "permalink": "https://www.instagram.com/p/" + media_id + "/"}


def receipt(media_id):
    return {"state": "published", "media_id": media_id,
            "verified_at": "2026-10-22T19:00:00-05:00",
            "permalink": "https://www.instagram.com/p/" + media_id + "/"}


class AuditTests(unittest.TestCase):
    def test_one_day_only_chicago_and_dst(self):
        self.assertEqual(audit.report_date(now=dt.datetime(2026, 11, 1, 2, tzinfo=audit.ZONE)),
                         dt.date(2026, 10, 31))
        self.assertEqual(audit.report_date("2026-10-22"), DAY)
        with self.assertRaises(ValueError):
            audit.report_date("10/22/26")
        self.assertTrue(audit.on_day(row("a", "FEED", "sample"), DAY))
        self.assertFalse(audit.on_day(row("b", "FEED", "sample", "01:00:00"), dt.date(2026, 10, 21)))

    def test_matching_live_posts_and_ledger_pass(self):
        rows = [row("a", "FEED", "Circus funny image"),
                row("b", "REELS", "Circus reel · 2026-10-22")]
        result = audit.assess(DAY, {str(DAY): receipt("a")},
                              {"jobs": {str(DAY): receipt("b")}}, rows)
        self.assertTrue(all(ok for ok, _ in result))

    def test_live_but_ledger_missing_is_not_called_absent(self):
        result = audit.assess(DAY, {}, {"jobs": {}},
                              [row("a", "FEED", "Circus funny image"),
                               row("b", "REELS", "Circus reel · 2026-10-22")])
        self.assertFalse(any(ok for ok, _ in result))
        self.assertTrue(all("LIVE" in detail for _, detail in result))

    def test_absent_posts_do_not_trigger_any_recovery(self):
        result = audit.assess(DAY, {}, {"jobs": {}}, [])
        self.assertEqual(sum(ok for ok, _ in result), 0)
        self.assertTrue(all("not confirmed" in detail for _, detail in result))

    def test_unidentified_reel_requires_review(self):
        result = audit.assess(DAY, {}, {"jobs": {}}, [row("other", "REELS", "no marker")])
        self.assertIn("unmarked", result[1][1])
        self.assertFalse(result[1][0])

    def test_luna_morning_post_does_not_count_as_circus_daily_image(self):
        result = audit.assess(DAY, {}, {"jobs": {}},
                              [row("a", "FEED", "Morning coffee with Luna Grace.")])
        self.assertFalse(result[0][0])

    def test_duplicate_images_fails_closed(self):
        result = audit.assess(DAY, {}, {"jobs": {}},
                              [row("a", "FEED", "Circus"), row("b", "FEED", "Circus")])
        self.assertIn("duplicates", result[0][1])

    def test_wrong_account_blocks_media_fetch(self):
        with patch.object(audit, "instagram_get", return_value={"username": "different", "user_id": "123"}) as get:
            with self.assertRaisesRegex(RuntimeError, "different account"):
                audit.live_media("fake", "123")
            get.assert_called_once()

    def test_http_401_explains_reauthorization(self):
        response = Mock(ok=False, status_code=401)
        response.json.return_value = {"error": {"code": 190}}
        with patch.object(audit.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "CIRCUS_IG_ACCESS_TOKEN"):
                audit.instagram_get("me", "fake", {})


if __name__ == "__main__":
    unittest.main()
