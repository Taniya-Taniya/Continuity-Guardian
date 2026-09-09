"""
Score Agent — attempts REAL music generation via Lyria, with a
guaranteed-working local fallback enabled by default.

HONEST CAVEAT: Lyria is primarily exposed through Vertex AI, not the
simple ai.google.dev API key most of this project uses. Rather than
block your demo on that setup, FALLBACK_MODE is ON by default: it
generates a short mood-tinted TONE locally (via Python's own `wave`
module, no external files, no API call, no dependencies) so this
agent always returns *something* playable.

This is obviously not real music — it's a placeholder so your demo
never shows a broken card. Swap in real Lyria access (see the
hackathon's "Lyria 3 Music Generation Guide") when you have time, or
drop your own royalty-free clips into
data/generated/scores/fallback/<mood>.wav — the fallback checks there
first before generating a tone.
"""

import math
import os
import struct
import wave
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "generated" / "scores"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FALLBACK_DIR = OUTPUT_DIR / "fallback"
FALLBACK_DIR.mkdir(exist_ok=True)

# ON by default — flip to "false" once you've wired up real Lyria access.
FALLBACK_MODE = os.environ.get("SCORE_AGENT_FALLBACK", "true").lower() == "true"

# Rough mood -> tone character mapping for the placeholder generator
MOOD_TONE_HZ = {
    "tense": 220, "urgent": 300, "quiet": 110, "neutral": 160,
    "clinical": 180, "sad": 130, "happy": 260, "romantic": 190,
}


def _generate_placeholder_tone(mood: str, out_path: Path, duration_sec: float = 4.0):
    """
    Synthesizes a simple fading sine tone, pitched by mood, as a
    stand-in music cue. Pure Python + stdlib `wave` — no dependencies,
    can never fail from a missing API key or quota.
    """
    sample_rate = 24000
    freq = MOOD_TONE_HZ.get(mood.lower().strip(), 160)
    n_samples = int(sample_rate * duration_sec)

    frames = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        fade = max(0.0, 1.0 - (t / duration_sec))  # fade out
        sample = math.sin(2 * math.pi * freq * t) * 0.2 * fade
        frames += struct.pack("<h", int(sample * 32767))

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


def _fallback_track_for_mood(mood: str) -> str:
    """Uses a user-supplied clip if one exists for this mood, else
    generates a placeholder tone on the spot."""
    candidate = FALLBACK_DIR / f"{mood.lower().strip()}.wav"
    if candidate.exists():
        return str(candidate)

    generated = OUTPUT_DIR / f"placeholder_{mood.lower().strip() or 'neutral'}.wav"
    if not generated.exists():
        _generate_placeholder_tone(mood, generated)
    return str(generated)


def generate_score(scene: dict) -> str:
    """
    Main entry point. Returns a local file path to a music track for
    this scene's mood.
    """
    mood = scene.get("mood", "neutral")

    if FALLBACK_MODE:
        return _fallback_track_for_mood(mood)

    # --- Real Lyria attempt ---
    # Lyria access typically goes through Vertex AI's music generation
    # endpoint rather than the plain google-genai client used
    # elsewhere in this project. Check the hackathon's "Lyria 3 Music
    # Generation Guide" link for the current call shape and wire it
    # in here once you've confirmed Vertex access.
    raise NotImplementedError(
        "Real Lyria call not wired up yet — see docstring above. "
        "Set env var SCORE_AGENT_FALLBACK=false only once you've "
        "actually implemented the real call below."
    )


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1]) as f:
        scene_data = json.load(f)

    print(generate_score(scene_data))
