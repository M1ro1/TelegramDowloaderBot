import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am"}
INSTAGRAM_PATH_PREFIXES = ("/p/", "/reel/", "/reels/", "/tv/")
TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
COOKIES_CANDIDATES = ("cokies.txt", "cookies.txt")


@dataclass(frozen=True)
class Settings:
    token: str
    max_requests: int = 3
    time_window: float = 2.0
    mute_duration: float = 10.0


def load_settings() -> Settings:
    token = os.getenv("TOKEN_BOT")
    if not token:
        raise RuntimeError("Environment variable TOKEN_BOT is not set.")
    return Settings(token=token)

