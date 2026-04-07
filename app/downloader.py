import glob
import os
import shutil
import subprocess
import tempfile
from typing import Optional

import yt_dlp

from .config import COOKIES_CANDIDATES, IMAGE_EXTENSIONS
from .url_filter import is_instagram_url

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def resolve_cookie_file() -> Optional[str]:
    for candidate in COOKIES_CANDIDATES:
        abs_path = os.path.abspath(candidate)
        if os.path.exists(abs_path):
            return abs_path
    return None


def detect_media_type(filepath: str) -> Optional[str]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "photo"
    elif ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def _resolve_entry_filepath(ydl, entry: dict, temp_dir: str) -> Optional[str]:
    if not isinstance(entry, dict):
        return None

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


def download_instagram_fallback(url: str, temp_dir: str, cookie_file: Optional[str]):
    print("yt-dlp could not extract this Instagram post. Trying gallery-dl fallback...")

    command = ["gallery-dl", "-d", temp_dir]
    if cookie_file:
        command.extend(["--cookies", cookie_file])
    command.append(url)

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        media_items = []

        for root, _, files in os.walk(temp_dir):
            for file_name in files:
                filepath = os.path.join(root, file_name)
                if os.path.isfile(filepath):
                    m_type = detect_media_type(filepath)
                    if m_type:
                        media_items.append({"path": filepath, "type": m_type})

        return media_items, {"uploader": "Instagram", "description": ""}
    except subprocess.CalledProcessError as error:
        print(f"gallery-dl error: {error.stderr}")
        return [], None
    except FileNotFoundError:
        print("gallery-dl is not installed. Install it with: pip install gallery-dl")
        return [], None


def download_media(url: str):
    temp_dir = tempfile.mkdtemp(prefix="tgdl_")
    ydl_opts = {
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 50_000_000,
        "noplaylist": False,
    }

    if not is_instagram_url(url):
        ydl_opts["format"] = "best"

    cookie_file = resolve_cookie_file()
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    media_items = []
    seen_paths = set()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not isinstance(info_dict, dict):
                return temp_dir, [], None

            entries = info_dict.get("entries")
            if entries:
                for entry in entries:
                    filepath = _resolve_entry_filepath(ydl, entry, temp_dir)
                    if filepath and filepath not in seen_paths:
                        seen_paths.add(filepath)
                        m_type = detect_media_type(filepath)
                        if m_type:
                            media_items.append({"path": filepath, "type": m_type})
            else:
                filepath = _resolve_entry_filepath(ydl, info_dict, temp_dir)
                if filepath:
                    seen_paths.add(filepath)
                    m_type = detect_media_type(filepath)
                    if m_type:
                        media_items.append({"path": filepath, "type": m_type})

            if not media_items:
                for filepath in glob.glob(os.path.join(temp_dir, "*")):
                    if not os.path.isfile(filepath) or filepath in seen_paths:
                        continue
                    seen_paths.add(filepath)
                    m_type = detect_media_type(filepath)
                    if m_type:
                        media_items.append({"path": filepath, "type": m_type})

            return temp_dir, media_items, info_dict
    except Exception as error:
        print(f"Download error: {error}")

        if is_instagram_url(url):
            try:
                media_items, fallback_info = download_instagram_fallback(url, temp_dir, cookie_file)
                if media_items:
                    return temp_dir, media_items, fallback_info
            except Exception as fallback_error:
                print(f"Instagram fallback error: {fallback_error}")

        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, [], None