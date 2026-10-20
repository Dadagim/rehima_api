import os
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from telegram_bot import get_bot_token, get_user_qr_payload_async


class TelegramBotUtilityTests(SimpleTestCase):
    def test_bot_token_prefers_telegram_bot_token(self):
        with patch.dict(
            os.environ,
            {
                'TELEGRAM_BOT_TOKEN': 'primary-token',
                'TELEGRAM_BOT_KEY': 'fallback-token',
            },
        ):
            self.assertEqual(get_bot_token(), 'primary-token')

    @patch('telegram_bot.get_user_qr_payload')
    def test_qr_lookup_runs_in_sync_adapter(self, lookup):
        lookup.return_value = (b'qr-image', 'Your QR code is ready.')

        result = async_to_sync(get_user_qr_payload_async)('member')

        self.assertEqual(result, (b'qr-image', 'Your QR code is ready.'))
        lookup.assert_called_once_with('member')
