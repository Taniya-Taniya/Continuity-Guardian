"""
Script Agent — REAL implementation, using the current google-genai SDK.

Takes a script PDF, extracts the raw text, then asks Gemini to structure
it into scenes matching data/schema/scene_schema.json.
"""

import json
import os

import pdfplumber

from config.models import TEXT_MODEL
from core.gemini_client import GeminiClient


gemini = GeminiClient(
    api_key=os.environ["GEMINI_API_KEY"],
    model=TEXT_MODEL,
)

EXTRACTION_PROMPT = """You are a script supervisor's assistant. Read the
following screenplay text and break it into scenes.

For EACH scene, output an object with exactly these fields:
- scene_id: the scene's slugline number if present, else "SC" + a
  sequential number (e.g. "SC001")
- script_text: the full text of that scene
- location: the slugline (e.g. "INT. WAREHOUSE - NIGHT")
- props: array of notable physical objects mentioned or implied
- wardrobe: object mapping character name -> notable clothing described
- mood: one or two words describing the scene's emotional tone
- dialogue: array of {{"speaker": ..., "line": ...}} for each line of dialogue

Return a JSON array of these scene objects.

SCREENPLAY TEXT:
---
{script_text}
---
"""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Pull raw text out of a script PDF."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def parse_script(pdf_path: str) -> list[dict]:
    """Parse a screenplay PDF into scene dictionaries."""
    script_text = extract_text_from_pdf(pdf_path)
    if not script_text.strip():
        raise ValueError(
            "No extractable text found in this PDF — is it a scanned image?"
        )

    response_text = gemini.generate(
        prompt=EXTRACTION_PROMPT.format(script_text=script_text),
        json_mode=True,
        retries=1,
    )

    try:
        scenes = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini didn't return valid JSON. Raw response:\n{response_text}"
        ) from exc

    if not isinstance(scenes, list):
        raise ValueError("Gemini returned JSON, but it was not a scene array.")

    for scene in scenes:
        scene.setdefault("takes", [])
        scene.setdefault("budget_complexity_score", None)
        scene.setdefault("storyboard_url", None)
        scene.setdefault("score_track_url", None)
        scene.setdefault("dub_tracks", {})
        scene.setdefault("captions", {})
        scene.setdefault("lock_status", "unlocked")

    return scenes


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python agent.py path/to/script.pdf")
        sys.exit(1)

    result = parse_script(sys.argv[1])
    print(json.dumps(result, indent=2))
