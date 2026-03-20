import unittest
from unittest.mock import patch

import requests

from notifier.telegram import redact_telegram_secrets, send_message


class TelegramNotifierTests(unittest.TestCase):
    def test_redact_telegram_secrets_masks_bot_token_in_url(self):
        raw = "HTTPSConnectionPool(host='api.telegram.org', port=443): /bot123456:ABCDEF/sendMessage"

        redacted = redact_telegram_secrets(raw)

        self.assertNotIn("123456:ABCDEF", redacted)
        self.assertIn("<telegram-token-redacted>", redacted)

    @patch("notifier.telegram.time.sleep")
    @patch("notifier.telegram.requests.post")
    def test_send_message_retries_transient_request_errors(self, post_mock, _sleep_mock):
        ok_response = unittest.mock.Mock()
        ok_response.raise_for_status.return_value = None
        post_mock.side_effect = [requests.exceptions.ConnectionError("dns failed"), ok_response]

        sent = send_message("test", retries=1, retry_delay=0)

        self.assertTrue(sent)
        self.assertEqual(post_mock.call_count, 2)

    @patch("notifier.telegram.time.sleep")
    @patch("notifier.telegram.requests.post")
    def test_send_message_raises_redacted_error_after_retries(self, post_mock, _sleep_mock):
        post_mock.side_effect = requests.exceptions.ConnectionError("/bot123456:ABCDEF/sendMessage dns failed")

        with self.assertRaises(RuntimeError) as exc:
            send_message("test", retries=1, retry_delay=0)

        self.assertIn("<telegram-token-redacted>", str(exc.exception))
        self.assertNotIn("123456:ABCDEF", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
