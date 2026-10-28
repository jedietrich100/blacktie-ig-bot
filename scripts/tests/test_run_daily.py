import datetime
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
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

    def test_generator_failure_never_renders_or_creates_assets(self):
        with patch.object(run_daily, "run", side_effect=RuntimeError("Generator exhausted")) as runner:
            with self.assertRaises(RuntimeError):
                run_daily.main()
        self.assertEqual(runner.call_count, 1)
        self.assertTrue(runner.call_args.args[0][-1].endswith("generate_quote.py"))
        self.assertFalse(self.image.exists())
        self.assertFalse(self.caption.exists())
        self.assertFalse((self.root / "scripts/_today_image_path.txt").exists())
        self.assertFalse((self.root / "scripts/_today_caption.txt").exists())

    def test_successful_subprocess_diagnostics_do_not_pollute_json(self):
        diagnostic = 'QUOTE_GENERATION: {"reason": "empty_text", "retrying": true}\n'
        result = SimpleNamespace(returncode=0, stdout='{"quote": "Valid quote."}\n', stderr=diagnostic)
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(run_daily.subprocess, "run", return_value=result), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            data = json.loads(run_daily.run(["test-generator"]))
        self.assertEqual(data["quote"], "Valid quote.")
        self.assertEqual(errors.getvalue(), diagnostic)
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()

