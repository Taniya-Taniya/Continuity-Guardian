"""
Budget Agent — REAL implementation. Deliberately rule-based, not
Gemini-based: budget-risk factors (cast size, locations, VFX) are
things you can count directly from the script data, so an LLM call
would just add latency and cost for no real benefit here. This also
means it has zero external dependencies — no API key needed, so it
can never be the thing that breaks during your demo.
"""

VFX_KEYWORDS = [
    "explosion", "green screen", "cgi", "vfx", "stunt", "fire",
    "crash", "helicopter", "gunfight", "chase",
]


def score_scene_budget(scene: dict) -> dict:
    """
    Returns {"budget_complexity_score": 0-10, "factors": [...]}
    so the UI/orchestrator can show *why* a scene scored the way it did,
    not just the number.
    """
    factors = []
    score = 0.0

    # Cast size — count unique speakers in dialogue
    speakers = {d.get("speaker") for d in scene.get("dialogue", []) if d.get("speaker")}
    cast_count = len(speakers)
    if cast_count >= 5:
        score += 3
        factors.append(f"Large cast in scene ({cast_count} speaking roles)")
    elif cast_count >= 3:
        score += 1.5
        factors.append(f"Medium cast in scene ({cast_count} speaking roles)")

    # Location complexity — EXT scenes and night shoots cost more
    location = (scene.get("location") or "").upper()
    if location.startswith("EXT."):
        score += 1.5
        factors.append("Exterior location — weather/permit dependent")
    if "NIGHT" in location:
        score += 1.5
        factors.append("Night shoot — lighting rig and crew overtime cost")

    # Prop complexity — more props = more continuity risk = more takes
    prop_count = len(scene.get("props", []) or [])
    if prop_count >= 4:
        score += 1.5
        factors.append(f"High prop count ({prop_count} tracked props)")

    # VFX/stunt keyword scan across script text + props
    haystack = " ".join(
        [scene.get("script_text", "") or ""] + (scene.get("props", []) or [])
    ).lower()
    matched_vfx = [kw for kw in VFX_KEYWORDS if kw in haystack]
    if matched_vfx:
        score += 2.5
        factors.append(f"VFX/stunt elements detected: {', '.join(matched_vfx)}")

    score = round(min(10.0, score), 1)
    if not factors:
        factors.append("No major cost-risk factors detected")

    return {"budget_complexity_score": score, "factors": factors}


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1]) as f:
        scene_data = json.load(f)
    print(json.dumps(score_scene_budget(scene_data), indent=2))
