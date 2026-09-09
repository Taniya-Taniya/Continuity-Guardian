# Data Schema

The single source of truth is `data/schema/scene_schema.json`. Every
agent reads from and writes to this shape — lock this down before
writing agent logic, since all 8 agents depend on it.

Key fields:
- `takes[].continuity_flags[]` — written by continuity_agent
- `takes[].risk_score` — written by continuity_agent
- `budget_complexity_score` — written by budget_agent
- `storyboard_url` / `score_track_url` / `dub_tracks` / `captions` —
  written by previz/score/localization/accessibility agents respectively
- `lock_status` — written only by the orchestrator, only after
  `continuity_check` and `budget_check` have both completed for the
  scene's current takes (see `agents/orchestrator/orchestrator.py::lock_scene`)
