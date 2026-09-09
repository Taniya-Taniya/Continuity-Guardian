"""
Performance Agent — REAL implementation.

Watches a take and compares the ACTUAL delivery tone/emotion of the
dialogue against the mood the script called for. Uses the same
video-understanding pattern as continuity_agent.
"""

import json
import os
import time

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

from config.models import FAST_MODEL
from core.gemini_client import GeminiClient


gemini = GeminiClient(
    api_key=os.environ["GEMINI_API_KEY"],
    model=FAST_MODEL,
)

PERFORMANCE_PROMPT = """You are a director reviewing a take. The
script calls for this scene's emotional tone to be: "{mood}"

Scripted dialogue for reference:
{dialogue}

Watch the attached take and assess how well the actual delivery
matches the intended tone. Return a JSON object with exactly these
fields:
- delivery_match_score: 0.0 to 1.0, how well delivery matched the
  intended mood (1.0 = perfect match)
- notes: a short, specific note on what you observed (e.g. "delivery
  reads flat/monotone where the script calls for tense urgency" or
  "delivery matches the intended tone well")
- flagged: true if delivery_match_score is below 0.6, else false
"""


def _upload_and_wait(video_path: str):
    video_file = client.files.upload(file=video_path)
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)
    if video_file.state.name == "FAILED":
        raise RuntimeError(f"Gemini failed to process video: {video_path}")
    return video_file


def assess_performance(scene: dict, take_video_path: str) -> dict:
    """
    Main entry point. Returns {"delivery_match_score", "notes", "flagged"}.
    """
    video_file = _upload_and_wait(take_video_path)

    dialogue_text = "\n".join(
        f'{d.get("speaker", "?")}: {d.get("line", "")}' for d in scene.get("dialogue", [])
    ) or "(no dialogue recorded for this scene)"

    prompt = PERFORMANCE_PROMPT.format(
        mood=scene.get("mood", "unspecified"),
        dialogue=dialogue_text,
    )

    response_text = gemini.generate(
        contents=[video_file, prompt],
        json_mode=True,
        retries=1,
    )

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini didn't return valid JSON. Raw response:\n{response.text}"
        ) from e

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python agent.py scene.json take.mp4")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        scene_data = json.load(f)

    print(json.dumps(assess_performance(scene_data, sys.argv[2]), indent=2))
