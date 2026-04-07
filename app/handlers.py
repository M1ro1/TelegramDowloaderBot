import re
import shutil
import threading
from html import escape

import telebot

from .antiflood import AntiFloodGuard
from .downloader import download_media
from .url_filter import is_instagram_url, is_supported_url, normalize_url


def safe_delete_message(bot: telebot.TeleBot, chat_id: int, message_id: int) -> None:
    try:
        bot.delete_message(chat_id, message_id)
    except telebot.apihelper.ApiTelegramException as error:
        print(f"Deleting error: {error}")


def build_caption(message, info: dict) -> str:
    raw_name = message.from_user.first_name or "User"
    user_id = message.from_user.id

    user_link = f'<a href="tg://user?id={user_id}">{escape(raw_name)}</a>'
    author = escape((info or {}).get("uploader") or "Unknown author")
    description = escape((info or {}).get("description") or "")

    caption = f"<b>From:</b> {user_link}\n<b>Author:</b> {author}"
    if description:
        caption += f"\n\n<blockquote expandable>{description[:800]}</blockquote>"
    return caption[:1024]


def send_media_items(bot: telebot.TeleBot, chat_id: int, media_items: list, caption: str) -> None:
    for index, item in enumerate(media_items):
        current_caption = caption if index == 0 else None
        with open(item["path"], "rb") as media_file:
            if item["type"] == "photo":
                bot.send_photo(
                    chat_id=chat_id,
                    photo=media_file,
                    caption=current_caption,
                    parse_mode="HTML" if current_caption else None,
                )
            else:
                bot.send_video(
                    chat_id=chat_id,
                    video=media_file,
                    caption=current_caption,
                    parse_mode="HTML" if current_caption else None,
                    supports_streaming=True,
                )


def register_handlers(bot: telebot.TeleBot, guard: AntiFloodGuard) -> None:
    @bot.message_handler(func=lambda message: True, content_types=["text"])
    def handle_links(message):
        text = message.text or ""
        urls = [normalize_url(url) for url in re.findall(r"(https?://[^\s]+)", text)]

        if not urls:
            return

        valid_urls = [url for url in urls if is_supported_url(url)]
        if not valid_urls:
            return

        user_id = message.from_user.id
        if guard.is_rate_limited(user_id):
            safe_delete_message(bot, message.chat.id, message.message_id)

            warn_text = (
                f"🛑 <a href='tg://user?id={user_id}'>{escape(message.from_user.first_name)}</a>, "
                f"too fast! Wait {int(guard.mute_duration)} seconds before the next link."
            )
            try:
                warn_msg = bot.send_message(message.chat.id, warn_text, parse_mode="HTML")
                threading.Timer(
                    guard.mute_duration,
                    safe_delete_message,
                    args=[bot, message.chat.id, warn_msg.message_id],
                ).start()
            except telebot.apihelper.ApiTelegramException:
                pass
            return

        processed_any = False

        for url in valid_urls:
            try:
                status_msg = bot.reply_to(message, "Downloading media...")
            except telebot.apihelper.ApiTelegramException:
                status_msg = bot.send_message(message.chat.id, "Downloading media...")

            temp_dir = None

            try:
                temp_dir, media_items, info = download_media(url)
                if not media_items:
                    fail_text = "Could not download media (private, unavailable, or too large)."
                    if is_instagram_url(url):
                        fail_text = "Instagram media is unavailable. Check that post is public and `cokies.txt` is valid."
                    try:
                        bot.edit_message_text(
                            fail_text,
                            chat_id=message.chat.id,
                            message_id=status_msg.message_id,
                        )
                    except telebot.apihelper.ApiTelegramException:
                        pass
                    continue

                caption = build_caption(message, info)
                send_media_items(bot, message.chat.id, media_items, caption)
                processed_any = True
            except Exception as error:
                print(f"Send error: {error}")
                bot.send_message(message.chat.id, "Error while sending media to Telegram.")
            finally:
                safe_delete_message(bot, message.chat.id, status_msg.message_id)
                if temp_dir:
                    shutil.rmtree(temp_dir, ignore_errors=True)

        if processed_any:
            safe_delete_message(bot, message.chat.id, message.message_id)
