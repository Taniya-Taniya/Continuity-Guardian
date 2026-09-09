"""
Localization Agent — REAL implementation.

Takes a scene's dialogue and generates a dubbed audio track in a
target language using Gemini's text-to-speech.

If you get a 404 model error, check aistudio.google.com for the
current TTS-capable model name and swap TTS_MODEL below.
"""

import os
import uuid
import wave
from pathlib import Path

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

from config.models import TTS_MODEL

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "generated" / "dubs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LANGUAGE_NAMES = {
    "es": "Spanish",
    "hi": "Hindi",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "pt": "Portuguese",
}


def _save_pcm_as_wav(pcm_data: bytes, out_path: Path, sample_rate: int = 24000):
    """Gemini TTS returns raw 16-bit PCM mono audio — wrap it in a WAV header."""
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)


def dub_scene(scene: dict, target_lang: str) -> str:
    """
    Main entry point. Returns a local file path to the dubbed WAV
    audio for this scene in target_lang (e.g. "es", "hi").
    """
    lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)

    dialogue_lines = scene.get("dialogue", [])
    if not dialogue_lines:
        raise ValueError("This scene has no dialogue to dub.")

    script_for_tts = "\n".join(
        f'{d.get("speaker", "Narrator")}: {d.get("line", "")}' for d in dialogue_lines
    )

    prompt = (
        f"Translate the following film dialogue into natural, spoken "
        f"{lang_name}, keeping each speaker's line separate, then read "
        f"it aloud with appropriate emotional delivery for a film scene "
        f"with mood '{scene.get('mood', 'neutral')}':\n\n{script_for_tts}"
    )

    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
        ),
    )

    audio_data = response.candidates[0].content.parts[0].inline_data.data
    filename = f"{scene.get('scene_id', 'scene')}_{target_lang}_{uuid.uuid4().hex[:8]}.wav"
    out_path = OUTPUT_DIR / filename
    _save_pcm_as_wav(audio_data, out_path)

    return str(out_path)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 3:
        print("Usage: python agent.py scene.json es")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        scene_data = json.load(f)

    path = dub_scene(scene_data, sys.argv[2])
    print(f"Saved dub to: {path}")
