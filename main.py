import glob
import os
import re
import shutil
import tempfile
from html import escape
from urllib.parse import urlparse

import telebot
import yt_dlp
from dotenv import load_dotenv

import time
import threading

# --- НАЛАШТУВАННЯ АНТИ-ФЛУДУ ---
# Якщо користувач надсилає більше MAX_REQUESTS повідомлень
# менш ніж за TIME_WINDOW секунд — він отримує "бан".
MAX_REQUESTS = 3
TIME_WINDOW = 2.0      # 2 секунди (тобто 3 повідомлення за 2 секунди = спам)
MUTE_DURATION = 10.0   # Тривалість блокування в секундах (зараз 10 сек)

# Зберігаємо час останніх запитів для кожного користувача
user_requests = {}
# Зберігаємо час, ДО якого користувач заблокований
muted_users = {}
# -------------------------------

load_dotenv()

TOKEN = os.getenv("TOKEN_BOT")
if not TOKEN:
    raise RuntimeError("Environment variable TOKEN_BOT is not set.")

bot = telebot.TeleBot(TOKEN)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def normalize_url(url):
    return url.rstrip(")],.!?:;\"'")


def is_supported_url(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    if host in INSTAGRAM_HOSTS or host in TIKTOK_HOSTS:
        return True

    if host == "youtu.be":
        return True

    if host in YOUTUBE_HOSTS and path.startswith("/shorts/"):
        return True

    return False


def safe_delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except telebot.apihelper.ApiTelegramException as e:
        print(f"Deleting error: {e}")


def detect_media_type(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "photo"
    return "video"


def build_caption(message, info):
    raw_name = message.from_user.first_name or "User"
    user_id = message.from_user.id

    safe_name = escape(raw_name)

    user_link = f'<a href="tg://user?id={user_id}">{safe_name}</a>'

    author = escape((info or {}).get("uploader") or "Unknown author")
    description = escape((info or {}).get("description") or "")

    caption = f"<b>From:</b> {user_link}\n<b>Author:</b> {author}"

    if description:
        caption += f"\n\n<blockquote expandable>{description[:800]}</blockquote>"

    return caption[:1024]

def _resolve_entry_filepath(ydl, entry, temp_dir):
    requested_downloads = entry.get("requested_downloads") or []
    for item in requested_downloads:
        filepath = item.get("filepath")
        if filepath and os.path.exists(filepath):
            return filepath

    prepared = ydl.prepare_filename(entry)
    if prepared and os.path.exists(prepared):
        return prepared

    media_id = entry.get("id")
    if media_id:
        matches = [
            path for path in glob.glob(os.path.join(temp_dir, f"{media_id}.*"))
            if os.path.isfile(path)
        ]
        if matches:
            return matches[0]

    return None


def download_media(url):
    temp_dir = tempfile.mkdtemp(prefix="tgdl_")
    ydl_opts = {
        "format": "best",
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 50_000_000,
    }

    media_items = []
    seen_paths = set()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            entries = info_dict.get("entries") if isinstance(info_dict, dict) else None
            if entries:
                for entry in entries:
                    if not entry:
                        continue
                    filepath = _resolve_entry_filepath(ydl, entry, temp_dir)
                    if filepath and filepath not in seen_paths:
                        seen_paths.add(filepath)
                        media_items.append({"path": filepath, "type": detect_media_type(filepath)})
            else:
                filepath = _resolve_entry_filepath(ydl, info_dict, temp_dir)
                if filepath:
                    media_items.append({"path": filepath, "type": detect_media_type(filepath)})

            return temp_dir, media_items, info_dict
    except Exception as error:
        print(f"Download error: {error}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, [], None


def check_spam(user_id):
    current_time = time.time()

    # 1. Перевіряємо, чи користувач зараз заблокований (в муті)
    if user_id in muted_users:
        if current_time < muted_users[user_id]:
            return True  # Все ще заблокований
        else:
            del muted_users[user_id]  # Час блокування вийшов, знімаємо мут

    # 2. Якщо не заблокований, перевіряємо частоту запитів
    if user_id not in user_requests:
        user_requests[user_id] = []

    # Залишаємо тільки ті запити, які були зроблені за останні TIME_WINDOW секунд
    user_requests[user_id] = [t for t in user_requests[user_id] if current_time - t < TIME_WINDOW]

    # Якщо за цей короткий час вже було забагато запитів — видаємо мут
    if len(user_requests[user_id]) >= MAX_REQUESTS:
        # Встановлюємо час закінчення блокування
        muted_users[user_id] = current_time + MUTE_DURATION
        # Очищаємо історію запитів, щоб після розблокування він почав з чистого аркуша
        user_requests[user_id] = []
        return True  # Користувач щойно був заблокований

    # Все добре, записуємо поточний запит і дозволяємо завантаження
    user_requests[user_id].append(current_time)
    return False

def send_media_items(chat_id, media_items, caption):
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


@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_links(message):
    text = message.text or ""
    urls = [normalize_url(url) for url in re.findall(r"(https?://[^\s]+)", text)]

    if not urls:
        return

    # Відбираємо тільки ті посилання, які ми вміємо завантажувати
    valid_urls = [url for url in urls if is_supported_url(url)]

    if not valid_urls:
        return

    # --- ПЕРЕВІРКА НА СПАМ ---
    user_id = message.from_user.id
    if check_spam(user_id):
        # Видаляємо повідомлення флудера
        safe_delete_message(message.chat.id, message.message_id)

        # Перевіряємо, чи ми вже попереджали його про цей конкретний мут.
        # Щоб не спамити попередженнями, якщо він продовжує строчити.
        # Для цього можна зробити просту перевірку, або просто надсилати одне повідомлення, яке видаляється.
        warn_text = f"🛑 <a href='tg://user?id={user_id}'>{escape(message.from_user.first_name)}</a>, занадто швидко! Почекайте {int(MUTE_DURATION)} секунд перед наступним посиланням."

        try:
            warn_msg = bot.send_message(message.chat.id, warn_text, parse_mode="HTML")
            # Видаляємо попередження якраз тоді, коли закінчується мут
            threading.Timer(MUTE_DURATION, safe_delete_message, args=[message.chat.id, warn_msg.message_id]).start()
        except telebot.apihelper.ApiTelegramException:
            pass  # Якщо бот не має прав писати

        return
    # -------------------------

    processed_any = False

    for url in valid_urls:

        if not is_supported_url(url):
            continue

        # БЕЗПЕЧНИЙ СТАТУС: Якщо оригінального повідомлення вже немає,
        # бот не впаде з помилкою, а просто надішле звичайне повідомлення.
        try:
            status_msg = bot.reply_to(message, "Downloading media...")
        except telebot.apihelper.ApiTelegramException:
            status_msg = bot.send_message(message.chat.id, "Downloading media...")

        temp_dir = None

        try:
            temp_dir, media_items, info = download_media(url)
            if not media_items:
                try:
                    bot.edit_message_text(
                        "Could not download media (private, unavailable, or too large).",
                        chat_id=message.chat.id,
                        message_id=status_msg.message_id,
                    )
                except telebot.apihelper.ApiTelegramException:
                    pass
                continue

            caption = build_caption(message, info)
            send_media_items(message.chat.id, media_items, caption)

            processed_any = True

        except Exception as error:
            print(f"Send error: {error}")
            bot.send_message(message.chat.id, "Error while sending media to Telegram.")
        finally:
            safe_delete_message(message.chat.id, status_msg.message_id)
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    if processed_any:
        safe_delete_message(message.chat.id, message.message_id)


print("Bot is running and waiting for links...")
bot.infinity_polling()