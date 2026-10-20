from django.core.management.base import BaseCommand

from telegram_bot import run_bot


class Command(BaseCommand):
    help = 'Starts the private Telegram bot that sends a user QR code to the requester privately.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Telegram bot...'))
        run_bot()
