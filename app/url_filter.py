from urllib.parse import urlparse

from .config import INSTAGRAM_HOSTS, INSTAGRAM_PATH_PREFIXES, TIKTOK_HOSTS, YOUTUBE_HOSTS


def normalize_url(url: str) -> str:
    return url.rstrip(")],.!?:;\"'")


def is_instagram_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return (parsed.hostname or "").lower() in INSTAGRAM_HOSTS


def is_supported_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    if host in INSTAGRAM_HOSTS:
        return any(path.startswith(prefix) for prefix in INSTAGRAM_PATH_PREFIXES)

    if host in TIKTOK_HOSTS:
        return True

    if host == "youtu.be":
        return True

    if host in YOUTUBE_HOSTS and path.startswith("/shorts/"):
        return True

    return False

