"""Offline regression tests for Buffer receipts that contain error statuses."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_buffer as image
import publish_buffer_reel as reel


class BufferStatusTests(unittest.TestCase):
    def test_error_receipt_is_rejected_for_images_and_reels_without_retry(self):
        for module, function, asset in ((image, image.publish, "image.jpg"),
                                        (reel, reel.publish_reel, "video.mp4")):
            for status in ("error", "failed"):
                with self.subTest(module=module.__name__, status=status):
                    result = {"data": {"createPost": {"post": {"id": "existing-receipt", "status": status}}}}
                    with patch.object(module, "gql", return_value=result) as gql:
                        with self.assertRaisesRegex(RuntimeError, "existing-receipt.*publication failed"):
                            function("test-key", "test-channel", asset, "Test caption")
                        gql.assert_called_once()

    def test_nonerror_receipt_is_acceptance_not_instagram_confirmation(self):
        for module, function, asset in ((image, image.publish, "image.jpg"),
                                        (reel, reel.publish_reel, "video.mp4")):
            result = {"data": {"createPost": {"post": {"id": "accepted-receipt", "status": "pending"}}}}
            with patch.object(module, "gql", return_value=result):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(function("test-key", "test-channel", asset, "Caption"), "accepted-receipt")

    def test_missing_id_and_mutation_errors_remain_failures(self):
        for module, function in ((image, image.publish), (reel, reel.publish_reel)):
            for payload in ({"post": {"status": "pending"}}, {"message": "connection expired"}):
                with patch.object(module, "gql", return_value={"data": {"createPost": payload}}):
                    with self.assertRaises(RuntimeError):
                        function("test-key", "test-channel", "asset", "Caption")
