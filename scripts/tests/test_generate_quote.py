"""Offline generator regression tests: no credentials, API calls, or publishing."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

import anthropic

SPEC = importlib.util.spec_from_file_location("generate_quote", Path(__file__).resolve().parents[1] / "generate_quote.py")
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)

QUOTE = "Machines can delegate decisions, but humans cannot delegate the consequences."
SECRET = "sensitive-canary-do-not-log"


def response(text=QUOTE, stop="end_turn", blocks=None):
    return SimpleNamespace(
        content=blocks if blocks is not None else [SimpleNamespace(type="text", text=text)],
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=100, output_tokens=12),
    )


def status_error(status):
    return anthropic.APIStatusError(
        SECRET, response=SimpleNamespace(request=object(), status_code=status,
                                         headers={"request-id": SECRET}),
        body={"error": {"message": SECRET}},
    )


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.sleeps = []
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        self.out = contextlib.redirect_stdout(self.stdout)
        self.err = contextlib.redirect_stderr(self.stderr)
        self.out.__enter__()
        self.err.__enter__()
        self.addCleanup(self.out.__exit__, None, None, None)
        self.addCleanup(self.err.__exit__, None, None, None)

    def generate(self, outcomes, recent=()):
        self.client.messages.create.side_effect = outcomes
        return generator.generate_quote(self.client, SECRET, recent, sleep=self.sleeps.append)

    def test_success_uses_same_model_and_single_request(self):
        self.assertEqual(self.generate([response()]), QUOTE)
        self.client.messages.create.assert_called_once_with(
            model="claude-sonnet-5", max_tokens=256,
            messages=[{"role": "user", "content": SECRET}],
        )
        self.assertEqual(self.sleeps, [])
        self.assertEqual(self.stdout.getvalue(), "")

    def test_empty_response_recovers_with_bounded_larger_budget(self):
        self.assertEqual(self.generate([response(""), response()]), QUOTE)
        self.assertEqual(self.sleeps, [2])
        calls = self.client.messages.create.call_args_list
        self.assertEqual([call.kwargs["max_tokens"] for call in calls], [256, 512])
        self.assertEqual(calls[0].kwargs["messages"], calls[1].kwargs["messages"])
        self.assertIn('"reason": "empty_text"', self.stderr.getvalue())
        self.assertNotIn(SECRET, self.stderr.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")

    def test_invalid_text_exhausts_exactly_three_attempts(self):
        for text in ("", " \n\t", '" "', "“”", "...", "one\ntwo", "one\rtwo", "word " * 21):
            with self.subTest(text=text):
                self.client.reset_mock()
                self.sleeps.clear()
                with self.assertRaises(RuntimeError):
                    self.generate([response(text)] * 3)
                self.assertEqual(self.client.messages.create.call_count, 3)
                self.assertEqual(self.sleeps, [2, 4])
                self.assertEqual([c.kwargs["max_tokens"] for c in self.client.messages.create.call_args_list], [256, 512, 512])

    def test_twenty_words_are_allowed(self):
        text = "word " * 20
        self.assertEqual(self.generate([response(text)]), text.strip())

    def test_quoted_text_and_outer_whitespace_are_cleaned(self):
        self.assertEqual(self.generate([response(' \n“' + QUOTE + '”\n')]), QUOTE)

    def test_text_blocks_are_combined_and_thinking_is_not_published(self):
        blocks = [SimpleNamespace(type="thinking", thinking=SECRET),
                  SimpleNamespace(type="text", text="Machines can delegate decisions, "),
                  SimpleNamespace(type="text", text="but humans cannot delegate the consequences.")]
        self.assertEqual(self.generate([response(blocks=blocks)]), QUOTE)
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_missing_malformed_and_non_text_content_retry_without_leaking(self):
        for blocks in ([], [SimpleNamespace(type="thinking", thinking=SECRET)],
                       [SimpleNamespace(type="text", text=None)], [{"text": SECRET}]):
            with self.subTest(blocks=blocks):
                self.assertEqual(self.generate([response(blocks=blocks), response()]), QUOTE)
        malformed = response()
        malformed.content = None
        self.assertEqual(self.generate([malformed, response()]), QUOTE)
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_truncated_nonempty_text_is_never_accepted(self):
        self.assertEqual(self.generate([response(SECRET, stop="max_tokens"), response()]), QUOTE)
        self.assertIn('"reason": "truncated_response"', self.stderr.getvalue())
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_valid_text_does_not_hide_a_malformed_text_block(self):
        blocks = [SimpleNamespace(type="text", text=QUOTE),
                  SimpleNamespace(type="text", text=None)]
        self.assertEqual(self.generate([response(blocks=blocks), response()]), QUOTE)
        self.assertEqual(self.client.messages.create.call_count, 2)
        self.assertIn('"reason": "invalid_content"', self.stderr.getvalue())

    def test_unexpected_blocks_fail_closed_even_alongside_valid_text(self):
        for kind in ("tool_use", "refusal", SECRET):
            with self.subTest(kind=kind):
                self.client.reset_mock()
                blocks = [SimpleNamespace(type="text", text=QUOTE),
                          SimpleNamespace(type=kind, text=SECRET)]
                with self.assertRaises(RuntimeError):
                    self.generate([response(blocks=blocks)])
                self.assertEqual(self.client.messages.create.call_count, 1)
        self.assertEqual(self.sleeps, [])
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_supported_redacted_thinking_is_never_published(self):
        blocks = [SimpleNamespace(type="redacted_thinking", data=SECRET),
                  SimpleNamespace(type="text", text=QUOTE)]
        self.assertEqual(self.generate([response(blocks=blocks)]), QUOTE)
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_refusal_and_unexpected_stop_reasons_fail_immediately(self):
        for stop in ("refusal", "tool_use", "pause_turn", "stop_sequence",
                     "model_context_window_exceeded", None, SECRET, {"bad": SECRET}):
            with self.subTest(stop=stop):
                self.client.reset_mock()
                with self.assertRaises(RuntimeError):
                    self.generate([response(SECRET, stop=stop)])
                self.assertEqual(self.client.messages.create.call_count, 1)
        self.assertEqual(self.sleeps, [])
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_normalized_duplicate_is_retried(self):
        duplicate = QUOTE.upper().replace(",", "—").replace(".", "!")
        alternative = "Automated choices travel faster than the institutions built to question them."
        self.assertEqual(self.generate([response(duplicate), response(alternative)], [QUOTE]), alternative)
        self.assertIn('"reason": "duplicate_quote"', self.stderr.getvalue())

    def test_transient_http_errors_retry(self):
        for status in (408, 409, 429, 500, 503, 529):
            with self.subTest(status=status):
                self.client.reset_mock()
                self.assertEqual(self.generate([status_error(status), response()]), QUOTE)
                self.assertEqual(self.client.messages.create.call_count, 2)
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_non_transient_http_errors_fail_immediately_without_sensitive_details(self):
        for status in (400, 401, 403, 404, 422):
            with self.subTest(status=status):
                self.client.reset_mock()
                with self.assertRaises(RuntimeError) as caught:
                    self.generate([status_error(status)])
                self.assertEqual(self.client.messages.create.call_count, 1)
                self.assertIsNone(caught.exception.__cause__)
                self.assertTrue(caught.exception.__suppress_context__)
                self.assertNotIn(SECRET, str(caught.exception))
        self.assertEqual(self.sleeps, [])
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_connection_and_timeout_errors_are_bounded(self):
        for error in (anthropic.APIConnectionError(message=SECRET, request=object()),
                      anthropic.APITimeoutError(request=object())):
            with self.subTest(error=type(error).__name__):
                self.client.reset_mock()
                self.sleeps.clear()
                with self.assertRaises(RuntimeError):
                    self.generate([error] * 3)
                self.assertEqual(self.client.messages.create.call_count, 3)
                self.assertEqual(self.sleeps, [2, 4])
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_other_sdk_errors_are_not_retried(self):
        error = anthropic.APIError(SECRET, request=object(), body={"secret": SECRET})
        with self.assertRaises(RuntimeError):
            self.generate([error])
        self.assertEqual(self.client.messages.create.call_count, 1)
        self.assertNotIn(SECRET, self.stderr.getvalue())

    def test_diagnostics_contain_safe_stop_usage_and_block_counts_only(self):
        message = response(blocks=[SimpleNamespace(type=SECRET, text=SECRET)], stop="max_tokens")
        message.usage = SimpleNamespace(input_tokens=SECRET, output_tokens=256)
        self.assertEqual(self.generate([message, response()]), QUOTE)
        diagnostic = json.loads(self.stderr.getvalue().split("QUOTE_GENERATION: ")[1])
        self.assertEqual(diagnostic["stop_reason"], "max_tokens")
        self.assertEqual(diagnostic["other_blocks"], 1)
        self.assertEqual(diagnostic["output_tokens"], 256)
        self.assertNotIn("input_tokens", diagnostic)
        self.assertNotIn(SECRET, self.stderr.getvalue())


class MainTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.history = root / "history.json"
        self.history.write_text('[{"quote": "An earlier thought.", "day": "monday"}]\n')
        self.before = self.history.read_bytes()
        self.themes = root / "themes.json"
        self.themes.write_text(json.dumps({day: {"theme": "Global Intel", "prompt": "Original theme prompt."}
                                          for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}))
        for name, value in (("HISTORY_PATH", str(self.history)), ("THEMES_PATH", str(self.themes))):
            patcher = patch.object(generator, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        patcher = patch.object(generator.anthropic, "Anthropic", return_value=self.client)
        self.constructor = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(generator.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.stdout, self.stderr = io.StringIO(), io.StringIO()

    def main(self):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            generator.main()

    def test_recovery_saves_history_once_and_stdout_remains_one_json_object(self):
        self.client.messages.create.side_effect = [response(""), response()]
        self.main()
        result = json.loads(self.stdout.getvalue())
        self.assertEqual(result["quote"], QUOTE)
        self.assertTrue(result["global_lens"])
        history = json.loads(self.history.read_text())
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["quote"], QUOTE)
        self.constructor.assert_called_once_with(max_retries=0, timeout=30.0)
        self.client.__exit__.assert_called_once()
        prompts = [call.kwargs["messages"] for call in self.client.messages.create.call_args_list]
        self.assertEqual(prompts[0], prompts[1])
        self.assertIn(generator.STYLE_GUIDE, prompts[0][0]["content"])
        self.assertIn(generator.GLOBAL_LENS_GUIDE, prompts[0][0]["content"])
        self.assertIn("An earlier thought.", prompts[0][0]["content"])

    def test_exhausted_generation_does_not_change_history_or_emit_a_result(self):
        self.client.messages.create.side_effect = [response("")] * 3
        with self.assertRaises(RuntimeError):
            self.main()
        self.assertEqual(self.history.read_bytes(), self.before)
        self.assertEqual(self.stdout.getvalue(), "")
        self.client.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
