import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("run_daily", Path(__file__).resolve().parents[1] / "run_daily.py")
run_daily = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_daily)


class AssetReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "docs/posts").mkdir(parents=True)
        self.day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        self.image = self.root / f"docs/posts/{self.day}.jpg"
        self.caption = self.root / f"docs/posts/{self.day}.caption.txt"
        self.here = patch.object(run_daily, "HERE", str(self.root / "scripts"))
        self.here.start()
        self.addCleanup(self.here.stop)

    def test_existing_assets_are_reused_without_generator(self):
        self.image.write_bytes(b"original image")
        self.caption.write_text("Original exact caption\nwith line breaks")
        with patch.object(run_daily, "run") as runner:
            run_daily.main()
        runner.assert_not_called()
        self.assertEqual(self.image.read_bytes(), b"original image")
        self.assertEqual((self.root / "scripts/_today_caption.txt").read_text(), self.caption.read_text())

    def test_partial_assets_are_never_regenerated(self):
        self.image.write_bytes(b"original image")
        with patch.object(run_daily, "run") as runner, self.assertRaises(RuntimeError):
            run_daily.main()
        runner.assert_not_called()

    def test_empty_caption_is_rejected(self):
        self.image.write_bytes(b"original image")
        self.caption.write_text(" ")
        with patch.object(run_daily, "run") as runner, self.assertRaises(RuntimeError):
            run_daily.main()
        runner.assert_not_called()

    def test_new_caption_is_durably_saved(self):
        data = {"quote": "A test insight.", "theme": "The Long View", "day": "sunday"}
        with patch.object(run_daily, "run", side_effect=[json.dumps(data), ""]):
            run_daily.main()
        self.assertEqual(self.caption.read_text(), run_daily.build_caption(data["quote"], data["theme"]))


if __name__ == "__main__":
    unittest.main()
