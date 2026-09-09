"""
Previz/Storyboard Agent — REAL implementation, with a free local
fallback ENABLED BY DEFAULT, since Gemini's image-generation models
often have a 0 free-tier quota (billing required) even with a valid
API key.

The fallback draws a simple placeholder storyboard locally with no
API call at all — guaranteed to work for your demo, just less
impressive visually than a real Gemini-generated sketch. Set env var
PREVIZ_AGENT_FALLBACK=false once you've confirmed billing/quota is
sorted, to use the real Gemini image call instead.

If you get a 404 "model not found" error on the real path, open
aistudio.google.com, check the current model list for an
image-generation model, and swap IMAGE_MODEL below — same issue we
hit with gemini-2.5-flash earlier.
"""

import os
import uuid
from pathlib import Path

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

IMAGE_MODEL = "gemini-2.5-flash-image"

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "generated" / "storyboards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FALLBACK_MODE = os.environ.get("PREVIZ_AGENT_FALLBACK", "true").lower() == "true"

STORYBOARD_PROMPT = """Black-and-white storyboard panel sketch, film
pre-production style, rough pencil linework. Scene: {location}.
Mood: {mood}. Key props/elements visible: {props}.
No text or captions in the image itself."""


def _draw_fallback_storyboard(scene: dict) -> str:
    """No API call — draws a simple placeholder panel with PIL so this
    agent can never be the thing that blocks your demo."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (960, 540), color=(28, 26, 24))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 940, 520], outline=(227, 162, 60), width=3)

    lines = [
        f"SCENE: {scene.get('location', '?')}",
        f"MOOD: {scene.get('mood', '?')}",
        f"PROPS: {', '.join(scene.get('props', []) or []) or 'none'}",
        "(placeholder — enable billing for a real Gemini sketch)",
    ]
    y = 220
    for line in lines:
        draw.text((60, y), line, fill=(237, 231, 221))
        y += 40

    filename = f"{scene.get('scene_id', 'scene')}_{uuid.uuid4().hex[:8]}_placeholder.png"
    out_path = OUTPUT_DIR / filename
    img.save(out_path)
    return str(out_path)


def generate_storyboard(scene: dict) -> str:
    """
    Main entry point. Generates one storyboard image for the scene
    and returns the local file path it was saved to.
    """
    if FALLBACK_MODE:
        return _draw_fallback_storyboard(scene)

    prompt = STORYBOARD_PROMPT.format(
        location=scene.get("location", "unspecified location"),
        mood=scene.get("mood", "neutral"),
        props=", ".join(scene.get("props", []) or []) or "none specified",
    )

    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            filename = f"{scene.get('scene_id', 'scene')}_{uuid.uuid4().hex[:8]}.png"
            out_path = OUTPUT_DIR / filename
            with open(out_path, "wb") as f:
                f.write(part.inline_data.data)
            return str(out_path)

    raise RuntimeError("Gemini returned no image data — check response for a text error message.")


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1]) as f:
        scene_data = json.load(f)

    path = generate_storyboard(scene_data)
    print(f"Saved storyboard to: {path}")
