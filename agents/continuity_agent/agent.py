"""
Continuity Agent — REAL implementation, on the current `google-genai`
SDK. This is the core feature.

Uploads two video takes to Gemini and asks it to find continuity
mismatches (props, wardrobe, lighting, dialogue) between them,
grounded in the scene's script data.

Requires: GEMINI_API_KEY in your .env
"""

import json
import os
import time

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

from config.models import FAST_MODEL
from core.gemini_client import GeminiClient


text_gemini = GeminiClient(
    api_key=os.environ["GEMINI_API_KEY"],
    model=FAST_MODEL,
)

COMPARISON_PROMPT = """You are a film continuity supervisor. You are
given two video takes of the SAME scene, plus that scene's script
data. Compare TAKE B against TAKE A and flag any continuity errors:
props in a different position/hand/state, wardrobe changes, lighting
or set-dressing differences, or dialogue that deviates from the
script.

SCENE DATA:
{scene_json}

Return a JSON array of flags found in TAKE B relative to TAKE A.
Each flag object must have exactly these fields:
- type: one of "prop", "wardrobe", "lighting", "dialogue"
- description: a short, specific description of the mismatch
- timestamp_sec: approximate second in TAKE B where it's visible
- confidence: your confidence in this flag, 0.0 to 1.0
- region: your best-guess bounding box of WHERE in the frame this is
  visible in TAKE B, as fractions of frame width/height (0.0-1.0):
  {{"x": left edge, "y": top edge, "width": ..., "height": ...}}.
  Approximate is fine — this is for drawing a rough highlight box,
  not pixel-perfect tracking.
- reasoning: one short sentence on what evidence grounds this flag —
  e.g. "script lists a coffee cup as a tracked prop; visible in
  Take A's right hand, absent from Take B's frame entirely."

If you find no continuity issues, return an empty array: []
"""


def _upload_and_wait(video_path: str):
    """Upload a video file to Gemini and wait until it's processed."""
    video_file = client.files.upload(file=video_path)
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)
    if video_file.state.name == "FAILED":
        raise RuntimeError(f"Gemini failed to process video: {video_path}")
    return video_file


def compare_takes(scene: dict, take_a_path: str, take_b_path: str) -> list[dict]:
    """
    Main entry point. Returns a list of flag dicts matching the
    continuity_flags shape in data/schema/scene_schema.json.
    """
    take_a_file = _upload_and_wait(take_a_path)
    take_b_file = _upload_and_wait(take_b_path)

    prompt = COMPARISON_PROMPT.format(
        scene_json=json.dumps(
            {
                "location": scene.get("location"),
                "props": scene.get("props"),
                "wardrobe": scene.get("wardrobe"),
                "dialogue": scene.get("dialogue"),
            },
            indent=2,
        )
    )

    response_text = text_gemini.generate(
        contents=[
            "TAKE A (reference):",
            take_a_file,
            "TAKE B (compare against A):",
            take_b_file,
            prompt,
        ],
        json_mode=True,
        retries=1,
    )

    try:
        flags = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini didn't return valid JSON. Raw response:\n{response.text}"
        ) from e

    return flags


def risk_score_from_flags(flags: list[dict]) -> float:
    """
    Simple weighted score, 0-10. Tune this once you have real data —
    right now it's just: more flags + higher confidence = higher risk.
    """
    if not flags:
        return 0.0
    total = sum(f.get("confidence", 0.5) for f in flags)
    return round(min(10.0, total * 3.0), 1)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python agent.py scene.json take_a.mp4 take_b.mp4")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        scene_data = json.load(f)

    result = compare_takes(scene_data, sys.argv[2], sys.argv[3])
    print(json.dumps(result, indent=2))
    print("Risk score:", risk_score_from_flags(result))
