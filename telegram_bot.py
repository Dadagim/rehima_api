import os

from asgiref.sync import sync_to_async


def get_bot_token():
    return os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_KEY')


def build_qr_image_payload(data: str, size: int = 10):
    import qrcode
    from io import BytesIO

    qr = qrcode.QRCode(version=1, box_size=size, border=5)
    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(fill_color='black', back_color='white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()


def get_user_qr_payload(username: str):
    from django.contrib.auth.models import User
    from config.core.models import MemberShip

    user = User.objects.filter(username=username).first()
    if user is None:
        return None, 'User not found.'

    membership = MemberShip.objects.filter(user=user).order_by('-start_date').first()
    if membership is None:
        return None, 'No membership QR code was found for this user.'

    if not membership.qr_code_image:
        membership.save()

    if not membership.qr_code_image:
        payload = str(membership.qr_token)
        return build_qr_image_payload(payload), 'Your QR code is ready.'

    with membership.qr_code_image.open('rb') as qr_file:
        return qr_file.read(), 'Your QR code is ready.'


async def get_user_qr_payload_async(username: str):
    return await sync_to_async(get_user_qr_payload, thread_sensitive=True)(username)


def run_bot():
    token = get_bot_token()
    if not token:
        raise RuntimeError('No Telegram bot token found. Set TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_KEY in the environment.')

    try:
        from telegram import InputFile, Update
        from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('python-telegram-bot is not installed. Install it in the backend environment.') from exc

    async def require_private_chat(update: Update):
        message = update.effective_message
        if message is None:
            return False

        chat = update.effective_chat
        if chat is None or chat.type != 'private':
            await message.reply_text('Please message me privately to request a QR code.')
            return False

        return True

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        if message is None:
            return
        if not await require_private_chat(update):
            return

        await message.reply_text(
            'Welcome! Send /qr <username> to get your private QR code, or send your username directly.'
        )

    async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        if message is None:
            return
        if not await require_private_chat(update):
            return

        username = ' '.join(context.args).strip()
        if username.startswith('@'):
            username = username[1:]
        if not username:
            await message.reply_text('Please send a username like: /qr your_username')
            return

        payload, response_text = await get_user_qr_payload_async(username)
        if payload is None:
            await message.reply_text(response_text)
            return

        await message.reply_photo(
            photo=InputFile(payload, filename='membership-qr.png'),
            caption=response_text,
        )

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        if message is None:
            return
        if not await require_private_chat(update):
            return

        username = message.text.strip()
        if username.startswith('@'):
            username = username[1:]
        if not username or username.startswith('/'):
            return

        payload, message_text = await get_user_qr_payload_async(username)
        if payload is None:
            await message.reply_text(message_text)
            return

        await message.reply_photo(
            photo=InputFile(payload, filename='membership-qr.png'),
            caption=message_text,
        )

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('qr', qr_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()


if __name__ == '__main__':
    import django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    run_bot()
