# Continuity Guardian

AI production co-pilot for film/TV. Two things live in this repo:

1. **The working app** — `agents/*/agent.py` + `api/main.py` +
   `frontend/` — a tested, real, end-to-end system you've already run
   and demoed. This is your primary demo path. Don't touch it while
   debugging the ADK layer below.
2. **ADK-native agents** — `agents/` — the same agent logic
   wrapped as real `google.adk.agents.Agent` objects, satisfying the
   hackathon's "build with Google ADK" requirement at the code level.
   This is additive, not a replacement — if it has issues, your
   working app in #1 is completely unaffected.

## ⚠️ Honest status of the two newest additions

Both of these were written without the ability to test them live (no
internet in the build environment) — they follow the documented APIs
precisely, but you should test them **early**, not the night before
your demo, so any issues surface with time to fix:

- **`agents/`** — real ADK `Agent` and `SequentialAgent` objects.
  If `adk web` or an import fails, it's almost always a small API
  version mismatch (ADK moves fast) — check `pip show google-adk` /
  the current ADK quickstart docs. Same class of fix as when we had
  to swap `gemini-2.5-flash` for `gemini-3.6-flash` earlier.
- **Clickhouse integration** — genuinely wired, not a stub: real
  HTTP push on every dashboard refresh, plus a live status endpoint
  the dashboard badge checks. But you need your own free Clickhouse
  Cloud account for it to have anything to connect to — see setup
  below.

## Run the main app (as before)

```bash
pip install -r requirements.txt --break-system-packages
cp .env.example .env
# paste your GEMINI_API_KEY into .env
py -3.14 -m uvicorn api.main:app --reload      # terminal 1
cd frontend && python3 -m http.server 5500     # terminal 2
```
Open http://localhost:5500 — same as always.

## Running the ADK-native agents

```bash
adk web agents
```
This opens ADK's own dev UI where you can chat with `script_agent`,
`continuity_agent`, or the full `orchestrator` pipeline directly, and
watch it call the real tools (parse_script, compare_takes, etc.) —
this is what you show a judge who wants to verify ADK usage
specifically, separate from the polished dashboard demo.

Alternatively, run one agent alone:
```bash
adk run agents/script_agent
```

If `adk` isn't recognized as a command after `pip install`, try:
```bash
py -3.14 -m google.adk.cli web agents
```
(entry point naming can vary by version — check `pip show
google-cloud-aiplatform` for what got installed).

## Setting up real Clickhouse (for a genuine partner integration)

1. Sign up for a free trial at clickhouse.com/cloud.
2. In the SQL console, run:
   ```sql
   CREATE TABLE continuity_guardian_metrics (
     ts DateTime,
     cost_avoided_usd UInt32,
     flags_today UInt32,
     scenes_locked UInt32,
     scenes_total UInt32
   ) ENGINE = MergeTree() ORDER BY ts;
   ```
3. From your Clickhouse Cloud service's "Connect" page, copy the
   HTTPS endpoint (looks like `https://<id>.clickhouse.cloud:8443/`)
   and your username/password.
4. In `.env`:
   ```
   CLICKHOUSE_URL=https://<id>.clickhouse.cloud:8443/
   CLICKHOUSE_USER=default
   CLICKHOUSE_PASSWORD=<your password>
   ```
5. Restart the backend. Reload the dashboard — the badge in the top
   header should flip from "not configured" to "connected ✓". If it
   says "connection failed," hover it for the exact error.
6. **To prove it live in your demo:** run a few scenes through the
   pipeline, then open your Clickhouse SQL console and run
   `SELECT * FROM continuity_guardian_metrics ORDER BY ts DESC LIMIT 10;`
   — showing a judge real rows landing in an external database as you
   use the app is a much stronger proof than the badge alone.
7. **Optional — visible in-app:** point a free Grafana Cloud
   dashboard at this Clickhouse table, then embed the panel's share
   URL in an `<iframe>` in `frontend/index.html` if you want it
   visible without switching tabs.

## Status of each agent (FastAPI side — the one you've tested)

| Agent | Status |
|---|---|
| Script Agent | Real |
| Continuity Agent | Real — core feature, includes region box + reasoning per flag |
| Performance Agent | Real |
| Budget Agent | Real, rule-based |
| Accessibility Agent | Real |
| Localization Agent | Real (needs a scene with actual dialogue) |
| Previz Agent | Real Gemini call + local fallback (default on) |
| Score Agent | Local fallback (default on); real Lyria not wired (Vertex-only) |
| Orchestrator | Forced-check lock rule + auto-drafted director notifications |

## Known constraints worth knowing before your demo

- Previz and Score run in fallback mode by default — a normal
  paid-tier constraint, not a project weakness.
- Localization/Accessibility need a scene with actual dialogue.
- `data/store/db.json` is your local "database" — reset to
  `{"scenes": []}` for a clean demo run.
- The ADK layer and Clickhouse integration are new and untested by
  me — budget time to verify them yourself before relying on them
  live.

## Project structure

```
continuity-guardian/
├── agents/                 # working, tested FastAPI-driven agents
├── agents/              # same logic, wrapped as real ADK Agents
│   ├── script_agent/agent.py
│   ├── continuity_agent/agent.py
│   ├── ... (one per agent)
│   └── orchestrator/agent.py   # real SequentialAgent: script → continuity → budget
├── api/main.py              # FastAPI backend + real Clickhouse push/status
├── data/
├── frontend/                # dashboard — now with a live Clickhouse badge
├── docs/
├── requirements.txt
└── .env.example
```

## Team role split

| Role | Owns |
|---|---|
| Backend/Agents Lead | `agents/*`, `api/main.py` |
| ADK/Platform Lead | `agents/*` — test early, verify against current ADK docs |
| Frontend/Dashboard Lead | `frontend/` |
| Data/Infra Lead | Clickhouse/Grafana setup |
| Product/Pitch Lead | README, demo script, pitch deck |
