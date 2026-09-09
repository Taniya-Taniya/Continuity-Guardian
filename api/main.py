"""
Continuity Guardian API — REAL implementation.

Storage: a local JSON file at data/store/db.json. This is deliberately
simple so the whole thing runs on one laptop with no cloud setup —
swap _load_db()/_save_db() for BigQuery/Firestore later without
touching any endpoint logic, since they all go through these two
functions.

Run it:
    pip install -r requirements.txt --break-system-packages
    cp .env.example .env   # add your GEMINI_API_KEY
    uvicorn api.main:app --reload
"""

import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from pydantic import BaseModel

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))  # so `agents.*` imports work when run directly

from agents.continuity_agent.agent import compare_takes, risk_score_from_flags
from agents.continuity_agent.frame_utils import extract_frame
from agents.script_agent.agent import parse_script
from agents.budget_agent.agent import score_scene_budget
from agents.performance_agent.agent import assess_performance
from agents.previz_agent.agent import generate_storyboard
from agents.score_agent.agent import generate_score
from agents.localization_agent.agent import dub_scene
from agents.accessibility_agent.agent import generate_captions, generate_audio_description
from agents.orchestrator.orchestrator import (
    draft_flag_notification,
    build_execution_plan,
)

DB_PATH = ROOT / "data" / "store" / "db.json"
UPLOAD_SCRIPTS = ROOT / "data" / "uploads" / "scripts"
UPLOAD_TAKES = ROOT / "data" / "uploads" / "takes"
UPLOAD_SCRIPTS.mkdir(parents=True, exist_ok=True)
UPLOAD_TAKES.mkdir(parents=True, exist_ok=True)

AVG_RESHOOT_COST_USD = 24000  # midpoint of $18k-$30k/day reshoot labor
COST_SOURCE = "DFI Rentals — 'Why Do Movies Do Reshoots?' (dfirentals.com)"

app = FastAPI(title="Continuity Guardian API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated images/audio (storyboards, scores, dubs, audio-desc)
GENERATED_DIR = ROOT / "data" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")


def _to_generated_url(local_path: str) -> str:
    """Turn an absolute local file path under data/generated into a URL the frontend can fetch."""
    rel = Path(local_path).resolve().relative_to(GENERATED_DIR.resolve())
    return f"/generated/{rel.as_posix()}"


# ---------------------------------------------------------------
# Real Clickhouse/Grafana push — a genuine partner-tool integration,
# not just a stub. Off by default (silently skipped) until you set
# CLICKHOUSE_URL/USER/PASSWORD in .env — see README for the free
# Clickhouse Cloud + Grafana Cloud setup steps. Once configured, every
# dashboard refresh pushes real rows into your Clickhouse table, and
# /api/integrations/clickhouse/status lets you PROVE it's live during
# a demo instead of it being an invisible background call.
# ---------------------------------------------------------------

CLICKHOUSE_URL = os.environ.get("CLICKHOUSE_URL", "").strip()
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "").strip()
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "").strip()


def _clickhouse_auth():
    if CLICKHOUSE_USER:
        return (CLICKHOUSE_USER, CLICKHOUSE_PASSWORD)
    return None


def _push_metrics_to_clickhouse(summary: dict) -> dict:
    """Returns {"attempted": bool, "success": bool, "error": str|None} —
    used by both the background push and the /status endpoint, so the
    same real result can be shown in the UI, not just logged silently."""
    if not CLICKHOUSE_URL:
        return {"attempted": False, "success": False, "error": None}

    query = (
        "INSERT INTO continuity_guardian_metrics "
        "(ts, cost_avoided_usd, flags_today, scenes_locked, scenes_total) VALUES "
        f"(now(), {summary['cost_avoided_usd']}, {summary['flags_today']}, "
        f"{summary['scenes_locked']}, {summary['scenes_total']})"
    )
    try:
        resp = requests.post(CLICKHOUSE_URL, data=query, auth=_clickhouse_auth(), timeout=5)
        resp.raise_for_status()
        return {"attempted": True, "success": True, "error": None}
    except Exception as e:
        return {"attempted": True, "success": False, "error": str(e)}


@app.get("/api/integrations/clickhouse/status")
def clickhouse_status():
    """Lets the dashboard show a real, provable connection status —
    not just 'we wrote the code for this.'"""
    if not CLICKHOUSE_URL:
        return {"configured": False, "reachable": False, "error": None}
    try:
        resp = requests.post(CLICKHOUSE_URL, data="SELECT 1", auth=_clickhouse_auth(), timeout=5)
        resp.raise_for_status()
        return {"configured": True, "reachable": True, "error": None}
    except Exception as e:
        return {"configured": True, "reachable": False, "error": str(e)}


def _load_db() -> dict:
    if not DB_PATH.exists():
        return {"scenes": []}
    with open(DB_PATH) as f:
        return json.load(f)


def _save_db(db: dict) -> None:
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


def _find_scene(db: dict, scene_id: str) -> dict:
    for scene in db["scenes"]:
        if scene["scene_id"] == scene_id:
            return scene
    raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")


# ---------------------------------------------------------------
# Script upload -> Script Agent
# ---------------------------------------------------------------

@app.post("/api/scripts/upload")
async def upload_script(file: UploadFile = File(...)):
    dest = UPLOAD_SCRIPTS / f"{uuid.uuid4().hex}_{file.filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        scenes = parse_script(str(dest))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Script parsing failed: {e}")

    db = _load_db()
    db["scenes"] = scenes  # replace — one script per project for now
    _save_db(db)

    return {"scenes_created": len(scenes), "scenes": scenes}

class AgentRunRequest(BaseModel):
    scene_id: str
    request: str

# ---------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------

@app.get("/api/scenes")
def list_scenes():
    return _load_db()["scenes"]


@app.get("/api/scenes/{scene_id}")
def get_scene(scene_id: str):
    return _find_scene(_load_db(), scene_id)


# ---------------------------------------------------------------
# Take upload -> Continuity Agent (runs once 2+ takes exist)
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/takes")
async def upload_take(scene_id: str, file: UploadFile = File(...)):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    dest = UPLOAD_TAKES / f"{scene_id}_{uuid.uuid4().hex}_{file.filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    take_id = len(scene["takes"]) + 1
    new_take = {
        "take_id": take_id,
        "video_url": str(dest),
        "continuity_flags": [],
        "risk_score": 0,
        "notification_draft": "",
    }

    # Always grab a "human view" thumbnail at ~1s so the dashboard has
    # something real to show, even before any check runs.
    thumb_path = GENERATED_DIR / "thumbnails" / f"{scene_id}_take{take_id}.png"
    if extract_frame(str(dest), 1.0, str(thumb_path)):
        new_take["thumbnail_url"] = _to_generated_url(str(thumb_path))

    scene["takes"].append(new_take)

    # Run continuity check as soon as there's something to compare against
    if len(scene["takes"]) >= 2:
        take_a = scene["takes"][0]
        try:
            flags = compare_takes(scene, take_a["video_url"], new_take["video_url"])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Continuity Agent failed: {e}")

        new_take["continuity_flags"] = flags
        new_take["risk_score"] = risk_score_from_flags(flags)
        scene["lock_status"] = "pending_checks"

        if flags:
            # "AI view" evidence frame — pulled at the first flag's own
            # timestamp, so it's the actual moment the mismatch is visible,
            # not just a generic 1-second grab.
            evidence_path = GENERATED_DIR / "thumbnails" / f"{scene_id}_take{take_id}_evidence.png"
            evidence_ts = flags[0].get("timestamp_sec", 1.0)
            if extract_frame(new_take["video_url"], evidence_ts, str(evidence_path)):
                new_take["evidence_thumbnail_url"] = _to_generated_url(str(evidence_path))

            new_take["notification_draft"] = draft_flag_notification(scene, flags)

    _save_db(db)
    return scene


# ---------------------------------------------------------------
# Lock — the forced-check rule lives here
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/lock")
def lock_scene(scene_id: str):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    if len(scene["takes"]) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 takes before this scene can be checked.",
        )

    latest_take = scene["takes"][-1]
    open_flags = latest_take.get("continuity_flags", [])
    if open_flags:
        raise HTTPException(
            status_code=409,
            detail=f"Blocked: {len(open_flags)} open continuity flag(s) on the latest take.",
        )

    scene["lock_status"] = "locked"
    _save_db(db)
    return scene


# ---------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------

@app.get("/api/dashboard/summary")
def dashboard_summary():
    scenes = _load_db()["scenes"]
    total_flags = sum(
        len(t.get("continuity_flags", [])) for s in scenes for t in s["takes"]
    )
    locked = sum(1 for s in scenes if s["lock_status"] == "locked")

    summary = {
        "cost_avoided_usd": total_flags * AVG_RESHOOT_COST_USD,
        "cost_source": COST_SOURCE,
        "flags_today": total_flags,
        "scenes_locked": locked,
        "scenes_total": len(scenes),
        "risk_by_day": [
            max((t.get("risk_score", 0) for t in s["takes"]), default=0) for s in scenes
        ],
    }
    _push_metrics_to_clickhouse(summary)
    return summary


# ---------------------------------------------------------------
# Budget Agent
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/budget")
def run_budget_check(scene_id: str):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    result = score_scene_budget(scene)
    scene["budget_complexity_score"] = result["budget_complexity_score"]
    scene["budget_factors"] = result["factors"]

    _save_db(db)
    return scene


# ---------------------------------------------------------------
# Performance Agent
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/performance")
def run_performance_check(scene_id: str):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    if not scene["takes"]:
        raise HTTPException(status_code=400, detail="Upload at least one take first.")

    latest_take = scene["takes"][-1]
    try:
        result = assess_performance(scene, latest_take["video_url"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Performance Agent failed: {e}")

    latest_take["performance"] = result
    _save_db(db)
    return scene


# ---------------------------------------------------------------
# Previz Agent
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/previz")
def run_previz(scene_id: str):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    try:
        local_path = generate_storyboard(scene)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Previz Agent failed: {e}")

    scene["storyboard_url"] = _to_generated_url(local_path)
    _save_db(db)
    return scene


# ---------------------------------------------------------------
# Score Agent
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/score")
def run_score(scene_id: str):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    try:
        local_path = generate_score(scene)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Score Agent failed: {e}")

    scene["score_track_url"] = _to_generated_url(local_path)
    _save_db(db)
    return scene


# ---------------------------------------------------------------
# Localization Agent
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/localize")
def run_localization(scene_id: str, lang: str = "es"):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    try:
        local_path = dub_scene(scene, lang)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Localization Agent failed: {e}")

    scene.setdefault("dub_tracks", {})
    scene["dub_tracks"][lang] = _to_generated_url(local_path)
    _save_db(db)
    return scene


# ---------------------------------------------------------------
# Accessibility Agent
# ---------------------------------------------------------------

@app.post("/api/scenes/{scene_id}/accessibility")
def run_accessibility(scene_id: str):
    db = _load_db()
    scene = _find_scene(db, scene_id)

    try:
        captions = generate_captions(scene)
        audio_desc = generate_audio_description(scene)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Accessibility Agent failed: {e}")

    scene.setdefault("captions", {})
    scene["captions"]["en"] = captions
    scene["captions"]["audio_description"] = audio_desc["text"]
    scene["captions"]["audio_description_url"] = _to_generated_url(audio_desc["audio_path"])

    _save_db(db)
    return scene

# ---------------------------------------------------------------
# CineVerse Agentic Orchestrator
# Runs only the agents required for the user's request
# ---------------------------------------------------------------

@app.post("/api/agent/run")
def run_agentic_workflow(payload: AgentRunRequest):
    """
    Natural-language entry point for CineVerse.

    The orchestrator examines the user's request and selects only
    the specialist agents that are actually required.
    """

    db = _load_db()
    scene = _find_scene(db, payload.scene_id)

    plan = build_execution_plan(payload.request)

    results = {}
    errors = {}

    for agent_name in plan["agents"]:

        try:

            # ---------------------------------------------------
            # Script Agent
            # ---------------------------------------------------
            # Script parsing already happens during upload.
            # We therefore reuse the current scene data instead
            # of calling Gemini again.
            if agent_name == "script":
                results["script"] = {
                    "status": "available",
                    "message": "Script analysis already exists for this project.",
                    "scene": scene,
                }

            # ---------------------------------------------------
            # Continuity Agent
            # ---------------------------------------------------
            elif agent_name == "continuity":

                if len(scene.get("takes", [])) < 2:
                    results["continuity"] = {
                        "status": "skipped",
                        "message": "Continuity requires at least two takes."
                    }
                else:
                    take_a = scene["takes"][0]
                    take_b = scene["takes"][-1]

                    flags = compare_takes(
                        scene,
                        take_a["video_url"],
                        take_b["video_url"],
                    )

                    risk = risk_score_from_flags(flags)

                    results["continuity"] = {
                        "status": "completed",
                        "flags": flags,
                        "risk_score": risk,
                        "flag_count": len(flags),
                    }

                    # Save the result so the normal dashboard
                    # can use it as well.
                    scene["takes"][-1]["continuity_flags"] = flags
                    scene["takes"][-1]["risk_score"] = risk

            # ---------------------------------------------------
            # Budget Agent
            # ---------------------------------------------------
            elif agent_name == "budget":

                budget_result = score_scene_budget(scene)

                scene["budget_complexity_score"] = (
                    budget_result["budget_complexity_score"]
                )

                scene["budget_factors"] = budget_result["factors"]

                results["budget"] = {
                    "status": "completed",
                    **budget_result,
                }

            # ---------------------------------------------------
            # Performance Agent
            # ---------------------------------------------------
            elif agent_name == "performance":

                if not scene.get("takes"):
                    results["performance"] = {
                        "status": "skipped",
                        "message": "Upload at least one take first."
                    }
                else:
                    latest_take = scene["takes"][-1]

                    performance_result = assess_performance(
                        scene,
                        latest_take["video_url"],
                    )

                    latest_take["performance"] = performance_result

                    results["performance"] = {
                        "status": "completed",
                        "result": performance_result,
                    }

            # ---------------------------------------------------
            # Previz Agent
            # ---------------------------------------------------
            elif agent_name == "previz":

                local_path = generate_storyboard(scene)

                scene["storyboard_url"] = _to_generated_url(local_path)

                results["previz"] = {
                    "status": "completed",
                    "storyboard_url": scene["storyboard_url"],
                }

            # ---------------------------------------------------
            # Accessibility Agent
            # ---------------------------------------------------
            elif agent_name == "accessibility":

                captions = generate_captions(scene)
                audio_desc = generate_audio_description(scene)

                scene.setdefault("captions", {})
                scene["captions"]["en"] = captions
                scene["captions"]["audio_description"] = audio_desc["text"]
                scene["captions"]["audio_description_url"] = (
                    _to_generated_url(audio_desc["audio_path"])
                )

                results["accessibility"] = {
                    "status": "completed",
                    "captions": captions,
                    "audio_description": audio_desc["text"],
                    "audio_description_url": scene["captions"][
                        "audio_description_url"
                    ],
                }

            # ---------------------------------------------------
            # Localization Agent
            # ---------------------------------------------------
            elif agent_name == "localization":

                # Default language for now.
                language = "es"

                local_path = dub_scene(scene, language)

                scene.setdefault("dub_tracks", {})
                scene["dub_tracks"][language] = _to_generated_url(local_path)

                results["localization"] = {
                    "status": "completed",
                    "language": language,
                    "dub_url": scene["dub_tracks"][language],
                }

            else:
                errors[agent_name] = "Unknown agent."

        except Exception as e:

            # One agent failing should NOT destroy the complete
            # CineVerse workflow.
            errors[agent_name] = str(e)

            results[agent_name] = {
                "status": "failed",
                "error": str(e),
            }

    _save_db(db)

    return {
        "status": "completed",
        "request": payload.request,
        "execution_plan": plan,
        "results": results,
        "errors": errors,
    }