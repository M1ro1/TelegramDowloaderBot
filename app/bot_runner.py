import telebot

from .antiflood import AntiFloodGuard
from .config import load_settings
from .handlers import register_handlers


def run() -> None:
    settings = load_settings()
    bot = telebot.TeleBot(settings.token)
    guard = AntiFloodGuard(
        max_requests=settings.max_requests,
        time_window=settings.time_window,
        mute_duration=settings.mute_duration,
    )

    register_handlers(bot, guard)
    print("Bot is running and waiting for links...")
    bot.infinity_polling()

