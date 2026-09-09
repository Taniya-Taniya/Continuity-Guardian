"""
Accessibility Agent — REAL implementation.

Generates: (1) plain English captions from a scene's dialogue, and
(2) a spoken audio-description track describing the key visual
action for visually impaired viewers.

If you get a 404 model error, check aistudio.google.com for current
model names and swap TEXT_MODEL/TTS_MODEL below.
"""

import os
import uuid
import wave
from pathlib import Path

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

from config.models import FAST_MODEL, TTS_MODEL
from core.gemini_client import GeminiClient


text_gemini = GeminiClient(
    api_key=os.environ["GEMINI_API_KEY"],
    model=FAST_MODEL,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "generated" / "accessibility"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_DESC_PROMPT = """You are writing an audio-description track for
visually impaired viewers. Based on this scene's data, write 2-3
short sentences describing the key VISUAL action a sighted viewer
would see (setting, character movement, important visual details) —
not the dialogue itself, since that's already audible. Keep it
concise enough to fit in natural pauses between lines.

SCENE DATA:
Location: {location}
Mood: {mood}
Props: {props}
Wardrobe: {wardrobe}
"""


def _save_pcm_as_wav(pcm_data: bytes, out_path: Path, sample_rate: int = 24000):
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)


def generate_captions(scene: dict) -> str:
    """Plain captions text, one line per spoken line."""
    dialogue = scene.get("dialogue", [])
    if not dialogue:
        return "(no dialogue in this scene)"
    return "\n".join(f'{d.get("speaker", "?")}: {d.get("line", "")}' for d in dialogue)


def generate_audio_description(scene: dict) -> dict:
    """
    Returns {"text": ..., "audio_path": ...} — the written description
    and a spoken WAV version of it.
    """
    prompt = AUDIO_DESC_PROMPT.format(
        location=scene.get("location", "unspecified"),
        mood=scene.get("mood", "neutral"),
        props=", ".join(scene.get("props", []) or []) or "none",
        wardrobe=scene.get("wardrobe", {}) or "none specified",
    )

    description_text = text_gemini.generate(
        prompt=prompt,
        retries=1,
    ).strip()

    audio_response = client.models.generate_content(
        model=TTS_MODEL,
        contents=description_text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
        ),
    )
    audio_data = audio_response.candidates[0].content.parts[0].inline_data.data

    filename = f"{scene.get('scene_id', 'scene')}_audiodesc_{uuid.uuid4().hex[:8]}.wav"
    out_path = OUTPUT_DIR / filename
    _save_pcm_as_wav(audio_data, out_path)

    return {"text": description_text, "audio_path": str(out_path)}


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1]) as f:
        scene_data = json.load(f)

    print("Captions:\n", generate_captions(scene_data))
    print("\nAudio description:\n", json.dumps(generate_audio_description(scene_data), indent=2))
