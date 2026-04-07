# TelegramDownloaderBot

Telegram bot for groups/chats: detects Instagram, TikTok, and YouTube Shorts links, downloads media, posts it back to the chat, and tries to delete the original message with the link.

## What the bot does
- Extracts URLs from text messages.
- Supports:
  - Instagram: posts, carousels, reels (`/p/`, `/reel/`, `/reels/`, `/tv/`)
  - TikTok
  - YouTube Shorts (`youtube.com/shorts`, `youtu.be`)
- Sends `photo` or `video` depending on media type.
- Includes anti-flood protection (temporary mute for spam-like bursts).
- Works with Instagram cookies (`cokies.txt` or `cookies.txt`).

## Project structure
- `main.py` - entrypoint.
- `app/bot_runner.py` - bot initialization and polling startup.
- `app/config.py` - environment config and shared constants.
- `app/url_filter.py` - URL normalization and supported-platform checks.
- `app/downloader.py` - download flow via `yt-dlp` + `gallery-dl` fallback for Instagram.
- `app/handlers.py` - Telegram handlers, caption building, send/delete flow.
- `app/antiflood.py` - anti-flood logic.

## Installation
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Configuration
Set your bot token in `.env`:

```env
TOKEN_BOT=your_telegram_bot_token_here
```

## Run
```powershell
python main.py
```

## Important for group usage
- For deleting user messages, the bot must be an admin with `can_delete_messages` permission.
- For Instagram posts/carousels, add a cookies file to the project root:
  - `cokies.txt` (supported with current filename)
  - or `cookies.txt`

## Dependencies
Main libraries:
- `pyTelegramBotAPI`
- `yt-dlp`
- `gallery-dl`
- `python-dotenv`

## Troubleshooting
- **Instagram does not download**: make sure the post is public and cookies are valid.
- **Bot cannot delete messages**: check bot admin permissions in the group.
- **Large files are not sent**: check Telegram Bot API size limits.
