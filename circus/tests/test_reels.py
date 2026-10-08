"""Regression checks for paid-call boundaries and uncertain publication outcomes."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("circus_reels", ROOT / "circus/reels/pipeline.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class ReelsTests(unittest.TestCase):
    def setUp(self):
        self.config = p.load_config()
        self.state = {"jobs": {}, "feed_days": {}, "paid_calls": {}}
        self.script = json.loads((p.HERE / "evergreen.json").read_text())[0]

    def test_bank_passes_and_repeats_are_blocked(self):
        for script in json.loads((p.HERE / "evergreen.json").read_text()):
            fingerprint = p.validate_script(script, self.config, self.state)
            self.state["jobs"][str(len(self.state["jobs"]))] = {"script": script, "script_hash": fingerprint}
            with self.assertRaisesRegex(RuntimeError, "Duplicate"):
                p.validate_script(script, self.config, self.state)

    def test_off_brand_script_is_rejected(self):
        self.script["pillar"] = "politics"
        with self.assertRaisesRegex(RuntimeError, "Off-brand"):
            p.validate_script(self.script, self.config, self.state)

    def test_reserve_exhaustion_never_repeats(self):
        self.state["jobs"] = {str(i): {"evergreen_index": i} for i in range(7)}
        with self.assertRaisesRegex(RuntimeError, "exhausted"):
            p.choose_evergreen(self.state)

    def test_dst_dates_and_delayed_runs(self):
        for day, cron in [("2026-10-31", "0,20,40 23 * * *"), ("2026-11-01", "0,20,40 0 * * *"),
                          ("2026-03-07", "0,20,40 0 * * *"), ("2026-03-08", "0,20,40 23 * * *")]:
            now = dt.datetime.fromisoformat(day + "T18:20:00").replace(tzinfo=p.ZONE)
            self.assertTrue(p.schedule_allowed(now, day, cron))
            self.assertFalse(p.schedule_allowed(now.replace(hour=19), day, cron))
            self.assertFalse(p.schedule_allowed(now, "2020-01-01", cron))
            self.assertFalse(p.schedule_allowed(now, day, "unknown"))

    def test_paid_calls_off_never_contact_provider(self):
        with patch.object(p.requests, "post") as post:
            with self.assertRaisesRegex(RuntimeError, "off"):
                p.paid_post("responses", self.config, self.state, "2026-10-08")
            post.assert_not_called()

    def test_paid_request_reserved_before_timeout_and_no_retry(self):
        self.config.update(paid_generation_enabled=True, max_paid_calls_per_day=1)
        with patch.dict(os.environ, {"CIRCUS_OPENAI_API_KEY": "fake"}), patch.object(p, "persist") as persist:
            def fail(*args, **kwargs):
                self.assertEqual(self.state["paid_calls"]["2026-10-08"], 1)
                persist.assert_called_once()
                raise TimeoutError()
            with patch.object(p.requests, "post", side_effect=fail) as post:
                with self.assertRaises(TimeoutError):
                    p.paid_post("responses", self.config, self.state, "2026-10-08")
                with self.assertRaisesRegex(RuntimeError, "limit reached"):
                    p.paid_post("responses", self.config, self.state, "2026-10-08")
                self.assertEqual(post.call_count, 1)

    def test_failed_durable_reservation_prevents_paid_call(self):
        self.config.update(paid_generation_enabled=True, max_paid_calls_per_day=9)
        with patch.dict(os.environ, {"CIRCUS_OPENAI_API_KEY": "fake"}), patch.object(p, "persist", side_effect=RuntimeError("push failed")), patch.object(p.requests, "post") as post:
            with self.assertRaisesRegex(RuntimeError, "push failed"):
                p.paid_post("responses", self.config, self.state, "2026-10-08")
            post.assert_not_called()

    def test_feed_freshness_and_future_dates(self):
        now = dt.datetime(2026, 10, 8, 12, tzinfo=dt.timezone.utc)
        xml = "<rss><channel>" + "".join(f"<item><title>Dog news</title><link>https://example.org/{i}</link><pubDate>{date}</pubDate></item>" for i, date in enumerate([
            "Thu, 08 Oct 2026 11:00:00 GMT", "Tue, 06 Oct 2026 11:00:00 GMT", "Fri, 09 Oct 2026 11:00:00 GMT", "invalid"])) + "</channel></rss>"
        self.assertEqual(len(p.fresh_feed_items(xml, now)), 1)

    def test_feed_reruns_exclude_today_from_baseline(self):
        current = dt.datetime(2026, 10, 8, 12, tzinfo=dt.timezone.utc)
        xml = "<rss><channel>" + "".join(f"<item><title>Dog story {i}</title><link>https://example.org/{i}</link><pubDate>Thu, 08 Oct 2026 11:00:00 GMT</pubDate></item>" for i in range(4)) + "</channel></rss>"
        self.state["feed_days"] = {"2026-10-07": {"pets": 1}}
        response = type("Response", (), {"content": xml, "raise_for_status": lambda self: None})()
        with patch.object(p.requests, "get", return_value=response):
            first = p.collect_topics(self.config, self.state, current)
            second = p.collect_topics(self.config, self.state, current)
        self.assertEqual(first, second)
        self.assertTrue(all(x["signal"] == "rising feed mentions" for x in first))

    def test_reconciliation_does_not_treat_noon_post_as_reel(self):
        marker = "Circus reel · 2026-10-08"
        self.assertIsNone(p.reconcile([{"id": "noon", "media_product_type": "FEED", "caption": marker}], marker))
        self.assertIsNone(p.reconcile([{"id": "old", "media_product_type": "REELS", "caption": "Circus reel · 2026-10-07"}], marker))
        self.assertEqual(p.reconcile([{"id": "yes", "media_product_type": "REELS", "caption": marker}], marker)["id"], "yes")

    def test_preview_does_not_call_api_or_write_durable_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, "render", return_value=Path(tmp)/"reel.mp4"), patch.object(p, "persist") as persist, patch.object(p.requests, "get") as get, patch.object(p.requests, "post") as post:
            p.run(preview=True, output=tmp)
            persist.assert_not_called()
            get.assert_not_called()
            post.assert_not_called()

    def test_wrong_account_stops_before_container_creation(self):
        self.config["publishing_enabled"] = True
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123"}), patch.object(p, "instagram", return_value={"username": "wrong", "user_id": "123"}) as api:
            with self.assertRaisesRegex(RuntimeError, "Wrong Instagram"):
                p.publish(self.config, self.state, "2026-10-08", ROOT, lambda: True)
            self.assertEqual(api.call_count, 1)

    def test_uncertain_publication_is_not_repeated(self):
        day = "2026-10-08"
        folder = ROOT / "docs/circus-reels" / day
        self.config["publishing_enabled"] = True
        self.state["jobs"][day] = {"state": "ready", "marker": "Circus reel · " + day, "media_commit": "abc", "caption": "joke", "container_id": "container"}
        calls = []
        saved = []
        def api(method, path, token, **kwargs):
            calls.append((method, path))
            if path == "me":
                return {"username": "circuspeanutsdaily", "user_id": "123"}
            if path == "123/media":
                return {"data": []}
            if path == "container":
                return {"status_code": "FINISHED"}
            if path == "123/media_publish":
                self.assertEqual(saved[-1]["jobs"][day]["state"], "submitting")
                raise TimeoutError()
            raise AssertionError(path)
        response = type("Response", (), {"ok": True, "content": b"0000ftyp"})()
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123", "GITHUB_REPOSITORY": "example/test"}), patch.object(p, "instagram", side_effect=api), patch.object(p.requests, "get", return_value=response), patch.object(p, "persist", side_effect=lambda state, *args: saved.append(copy.deepcopy(state))):
            with self.assertRaises(TimeoutError):
                p.publish(self.config, self.state, day, folder, lambda: True)
            with self.assertRaisesRegex(RuntimeError, "no blind retry"):
                p.publish(self.config, self.state, day, folder, lambda: True)
        self.assertEqual(calls.count(("POST", "123/media_publish")), 1)

    def test_disabled_publication_makes_no_requests(self):
        with patch.object(p, "instagram") as api:
            p.publish(self.config, self.state, "2026-10-08", ROOT, lambda: True)
            api.assert_not_called()

    def test_uncertain_container_is_blocked_and_can_reconcile_live_reel(self):
        day = "2026-10-08"
        self.config["publishing_enabled"] = True
        self.state["jobs"][day] = {"state": "creating_container", "marker": "Circus reel · " + day}
        rows = []
        def api(method, path, token, **kwargs):
            if path == "me":
                return {"username": "circuspeanutsdaily", "user_id": "123"}
            if path == "123/media":
                return {"data": rows}
            raise AssertionError("No POST expected")
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123"}), patch.object(p, "instagram", side_effect=api), patch.object(p, "persist"):
            with self.assertRaisesRegex(RuntimeError, "no blind retry"):
                p.publish(self.config, self.state, day, ROOT, lambda: True)
            rows.append({"id": "live", "caption": "Circus reel · " + day, "media_product_type": "REELS", "permalink": "https://example.invalid/live"})
            p.publish(self.config, self.state, day, ROOT, lambda: True)
        self.assertEqual(self.state["jobs"][day]["media_id"], "live")

    def test_missing_insights_are_not_recorded_as_zero(self):
        self.state["jobs"]["2026-10-07"] = {"state": "published", "media_id": "live"}
        def api(method, path, token, **kwargs):
            if path == "me":
                return {"username": "circuspeanutsdaily", "user_id": "123"}
            if kwargs["params"]["metric"] == "views":
                return {"data": [{"values": [{"value": 12}]}]}
            raise RuntimeError("Permission missing")
        with patch.dict(os.environ, {"CIRCUS_IG_ACCESS_TOKEN": "fake", "CIRCUS_IG_USER_ID": "123"}), patch.object(p, "instagram", side_effect=api), patch.object(p, "persist"):
            p.collect_metrics(self.state, dt.datetime(2026, 10, 8, 18, tzinfo=p.ZONE))
        snapshot = self.state["jobs"]["2026-10-07"]["metrics"]["24h"]
        self.assertEqual(snapshot["views"], 12)
        self.assertNotIn("reach", snapshot)
        self.assertIn("reach", snapshot["unavailable"])


if __name__ == "__main__":
    unittest.main()
