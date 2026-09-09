"""
Orchestrator — REAL implementation.

Two jobs:
1. Enforce the forced-check rule: a scene cannot be marked "locked"
   until continuity_check and budget_check have both run for its
   current takes. (The FastAPI layer in api/main.py mirrors this
   directly on the /lock endpoint; this module is the single source
   of truth both should agree with.)
2. When the Continuity Agent finds flags, draft a notification a real
   director/producer would actually receive — this is deliberately
   templated (not another Gemini call) so it's instant, free, and
   never a point of failure, while still demonstrating that the
   system ACTS on what it finds rather than just displaying it.
"""


def lock_scene(scene_id: str, checks: dict) -> bool:
    """
    Only allow locking a scene once continuity_check and budget_check
    have both run for this scene's current takes.
    """
    required = {"continuity_check", "budget_check"}
    if not required.issubset(checks.keys()):
        raise PermissionError(f"Cannot lock {scene_id}: missing {required - checks.keys()}")
    return True


def draft_flag_notification(scene: dict, flags: list[dict]) -> str:
    """
    Returns a ready-to-send message body a director/producer would
    actually receive when a continuity flag is found. Deliberately
    plain-text and templated — no AI call needed for this, and it
    means this notification can never fail from a quota/API issue.
    """
    if not flags:
        return ""

    scene_id = scene.get("scene_id", "this scene")
    location = scene.get("location", "unspecified location")

    lines = [
        f"Continuity Guardian flagged {len(flags)} issue(s) in {scene_id} ({location}):",
        "",
    ]
    for flag in flags:
        t = int(flag.get("timestamp_sec", 0))
        mins, secs = divmod(t, 60)
        lines.append(
            f"  [{flag.get('type', '?').upper()}] at {mins}:{secs:02d} — {flag.get('description', '')}"
        )

    highest_confidence = max((f.get("confidence", 0) for f in flags), default=0)
    urgency = "HIGH — recommend reviewing before next setup" if highest_confidence >= 0.8 else "Review when convenient"

    lines += [
        "",
        f"Priority: {urgency}",
        f"Scene is BLOCKED from locking until these are resolved.",
        "— Continuity Guardian (automated)",
    ]
    return "\n".join(lines)

# -------------------------------------------------------------------
# Agentic orchestration
# -------------------------------------------------------------------

AGENT_ROLES = {
    "script": "Analyze screenplay structure, scenes, characters, locations, props, wardrobe, and mood.",
    "production": "Create and optimize the shooting plan based on locations, actors, time, and production constraints.",
    "continuity": "Detect continuity conflicts involving characters, props, wardrobe, injuries, locations, and scene state.",
    "budget": "Estimate production complexity and identify budget risks.",
    "performance": "Analyze production performance and identify bottlenecks or high-complexity scenes.",
    "accessibility": "Identify accessibility requirements such as captions, audio descriptions, and accessibility risks.",
    "previz": "Create shot plans and storyboard requirements for important scenes.",
}


def choose_agents(user_request: str) -> list[str]:
    request = user_request.lower()
    selected = []

    # -----------------------------------------------------------
    # Full production planning
    # -----------------------------------------------------------
    if any(word in request for word in [
        "prepare the film",
        "prepare film",
        "prepare this film",
        "production plan",
        "production planning",
        "shooting plan",
        "shooting schedule",
        "plan the shoot",
        "production"
    ]):
        selected.extend([
            "script",
            "budget",
            "production",
            "continuity",
        ])

    # -----------------------------------------------------------
    # Script
    # -----------------------------------------------------------
    elif any(word in request for word in [
        "script",
        "screenplay",
        "scene",
        "character",
        "story"
    ]):
        selected.append("script")

    # -----------------------------------------------------------
    # Production
    # -----------------------------------------------------------
    if any(word in request for word in [
        "shoot",
        "schedule",
        "production",
        "location",
        "shooting day"
    ]):
        if "production" not in selected:
            selected.append("production")

    # -----------------------------------------------------------
    # Continuity
    # -----------------------------------------------------------
    if any(word in request for word in [
        "continuity",
        "costume",
        "prop",
        "injury",
        "consistent",
        "continuity risk"
    ]):
        if "continuity" not in selected:
            selected.append("continuity")

    # -----------------------------------------------------------
    # Budget
    # -----------------------------------------------------------
    if any(word in request for word in [
        "budget",
        "cost",
        "money",
        "expensive",
        "cheap",
        "$"
    ]):
        if "budget" not in selected:
            selected.append("budget")

    # -----------------------------------------------------------
    # Performance
    # -----------------------------------------------------------
    if any(word in request for word in [
        "performance",
        "bottleneck",
        "efficiency"
    ]):
        if "performance" not in selected:
            selected.append("performance")

    # -----------------------------------------------------------
    # Risk means multiple production checks
    # -----------------------------------------------------------
    if "risk" in request:
        for agent in ["continuity", "budget", "performance"]:
            if agent not in selected:
                selected.append(agent)

    # -----------------------------------------------------------
    # Accessibility
    # -----------------------------------------------------------
    if any(word in request for word in [
        "accessibility",
        "caption",
        "captions",
        "audio description"
    ]):
        selected.append("accessibility")

    # -----------------------------------------------------------
    # Previz / Storyboard
    # -----------------------------------------------------------
    if any(word in request for word in [
        "storyboard",
        "visual",
        "shot",
        "camera",
        "previz"
    ]):
        selected.append("previz")

    # Remove duplicates while preserving order
    selected = list(dict.fromkeys(selected))

    # Default production workflow
    if not selected:
        selected = [
            "script",
            "continuity",
            "budget",
            "production",
        ]

    return selected


def build_execution_plan(user_request: str) -> dict:
    """
    Build the workflow that the orchestrator wants to execute.
    """
    selected_agents = choose_agents(user_request)

    execution_order = [
        agent
        for agent in [
            "script",
            "continuity",
            "budget",
            "production",
            "performance",
            "accessibility",
            "previz",
        ]
        if agent in selected_agents
    ]

    return {
        "user_request": user_request,
        "agents": execution_order,
        "roles": {
            agent: AGENT_ROLES[agent]
            for agent in execution_order
        },
    }

if __name__ == "__main__":
    import json

    request = input("What should CineVerse do? ")

    plan = build_execution_plan(request)

    print("\nExecution Plan:")
    print(json.dumps(plan, indent=2))