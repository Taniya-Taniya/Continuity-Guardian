import os

TEXT_MODEL = os.getenv("TEXT_MODEL", "gemini-3.6-flash")
FAST_MODEL = os.getenv("FAST_MODEL", "gemini-3.5-flash-lite")

TTS_MODEL = os.getenv(
    "TTS_MODEL",
    "gemini-2.5-flash-preview-tts"
)

IMAGE_MODEL = os.getenv(
    "IMAGE_MODEL",
    "gemini-2.5-flash-image"
)