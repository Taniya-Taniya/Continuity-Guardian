# Continuity Guardian

**An AI production co-pilot for film & TV** — it reads a script, watches
dailies, and catches continuity errors between takes (a prop in the wrong
hand, a jacket that's zipped in one take and not the next) before they turn
into an expensive reshoot. Built with Gemini and a real multi-agent
pipeline.

Most AI-in-film demos generate content — scripts, trailers, images. This
does the opposite: it's an operations/QA tool for the boring, expensive part
of production nobody's agentified yet.

---

## What it does

A script goes in. Video takes go in. Out comes:

- **Continuity flags with visual evidence** — Gemini compares two takes of
  the same scene against the script, flags prop/wardrobe/lighting/dialogue
  mismatches, and returns a bounding-box region for each one. The dashboard
  extracts the actual frame at that timestamp and draws the box on it.
- **Explainability** — every flag includes the model's own reasoning for
  why it was raised, not just a verdict.
- **A forced-check lock rule** — a scene can't be marked "done" until
  continuity + budget checks have both run, mirroring a real script
  supervisor's sign-off process.
- **The orchestrator takes action** — when a flag is found, it auto-drafts
  a ready-to-send notification for the director, not just a dashboard number.
- **Performance notes** — does the actual delivery match the emotional tone
  the script called for?
- **Budget-risk scoring** — cast size, night shoots, VFX keywords, scored
  straight from the script, no AI call needed.
- **A cited cost-avoided metric**, grounded in a published reshoot-cost
  estimate rather than an arbitrary number.
- **Auto-generated previz, temp score, captions, and multi-language dubs**
  as a byproduct of the same pipeline.
- **Optional real Clickhouse integration** — live metrics push to an
  external database, with a status badge in the UI proving the connection
  is real, not just present in the code.

## Architecture

```
                 WEB DASHBOARD (frontend/)
     Upload script/takes · view flags + evidence · post-production panel
                        │
                 ORCHESTRATOR (agents/orchestrator)
     Forced-check lock rule + auto-drafted director notifications
   ┌────┬────┬─────┬──────┬───────┬───────┬────────┬────────┐
 Script Cont Perf Budget Previz  Score  Localize  Access-
 Agent  Agent Agent Agent Agent   Agent   Agent    ibility
   └────┴────┴─────┴──────┴───────┴───────┴────────┴────────┘
                        │
        core/gemini_client.py — shared, retry-safe Gemini client
        config/models.py — centralized model name configuration
                        │
              Local JSON store (data/store/db.json)
                        │
        (optional) Clickhouse — live metrics for a real external dashboard
```

Each agent is a plain Python function with a single responsibility,
reading/writing a shared `Scene` object defined in
[`data/schema/scene_schema.json`](data/schema/scene_schema.json). Gemini
calls go through a shared `GeminiClient` (`core/gemini_client.py`) with
built-in quota-error backoff, and model names are centralized in
`config/models.py` rather than hardcoded per agent. See
[`docs/architecture.md`](docs/architecture.md) for more detail.

## Status of each agent

| Agent | Status |
|---|---|
| Script Agent | Real — parses a script PDF into structured scenes via Gemini |
| Continuity Agent | Real — core feature; compares two takes via Gemini video understanding, returns region + reasoning per flag |
| Performance Agent | Real — compares delivery tone against the script's intended mood |
| Budget Agent | Real — rule-based, no API call needed |
| Accessibility Agent | Real — auto-captions + spoken audio-description via Gemini TTS |
| Localization Agent | Real — Gemini TTS dub into a target language (needs a scene with actual dialogue) |
| Previz Agent | Real Gemini image call, defaults to a local placeholder (image gen often needs Cloud billing enabled) |
| Score Agent | Defaults to a local placeholder tone (real Lyria integration is Vertex-only, not wired up) |
| Orchestrator | Forced-check lock rule + auto-drafted director notifications |

## Getting started

**Requirements:** Python 3.10+, a free Gemini API key from
[aistudio.google.com](https://aistudio.google.com/app/apikey)

```bash
pip install -r requirements.txt
cp .env.example .env
# paste your GEMINI_API_KEY into .env
```

**Run the backend:**
```bash
uvicorn api.main:app --reload
```
Interactive API docs at http://localhost:8000/docs

**Run the frontend** (separate terminal):
```bash
cd frontend
python3 -m http.server 5500
```
Open http://localhost:5500 — upload a script PDF, select a scene, upload
two video takes, and try the post-production agents panel.

> Multiple Python versions installed (common on Windows)? Check `py -0p`
> and use the same interpreter for every command, e.g.
> `py -3.14 -m pip install -r requirements.txt`.

### Optional: real Clickhouse integration

Set `CLICKHOUSE_URL`, `CLICKHOUSE_USER`, and `CLICKHOUSE_PASSWORD` in
`.env` to push live metrics to a real Clickhouse instance (a free
Clickhouse Cloud trial works). The dashboard's header badge will show
"connected ✓" once it's reachable. See `docs/architecture.md` for the
one-time table setup. Leave unset to skip — the app works fully without it.

## Known constraints

- **Previz and Score run in fallback/placeholder mode by default.** This
  is intentional — image and music generation typically need billing
  enabled on a Google Cloud project even with a valid API key. The
  pipeline and prompts for real generation are already written; swapping
  in real access later is a configuration change, not a redesign.
- **Localization/Accessibility need a scene with actual spoken dialogue**
  to produce non-empty output — a purely visual-description scene will
  correctly report "no dialogue," not error.
- **Gemini model names change over time.** If a call 404s with a "model no
  longer available" message, check the current model list at
  aistudio.google.com and update the relevant constant in
  `config/models.py`.
- `data/store/db.json` is the entire local "database" for this prototype —
  reset it to `{"scenes": []}` for a clean run.

## Project structure

```
continuity-guardian/
├── agents/
│   ├── orchestrator/          # forced-check lock rule + notification drafting
│   ├── script_agent/          # PDF → structured scene data
│   ├── continuity_agent/      # core feature — region + reasoning per flag
│   ├── performance_agent/
│   ├── budget_agent/
│   ├── previz_agent/
│   ├── score_agent/
│   ├── localization_agent/
│   └── accessibility_agent/
├── core/
│   └── gemini_client.py        # shared, retry-safe Gemini client
├── config/
│   └── models.py                # centralized model name configuration
├── api/main.py                  # FastAPI backend + optional Clickhouse push
├── data/
│   ├── schema/scene_schema.json    # the shared data contract every agent uses
│   ├── store/db.json               # local "database"
│   ├── uploads/{scripts,takes}/
│   └── generated/{storyboards,scores,dubs,accessibility,thumbnails}/
├── frontend/                   # dashboard — HTML/CSS/JS, no framework
├── docs/{architecture.md, schema.md}
├── requirements.txt
└── .env.example
```

## Roadmap

- [ ] Real Imagen/Lyria generation once Cloud billing is configured
- [ ] Migrate `data/store` to BigQuery/Firestore
- [ ] Deploy agents on Vertex AI Agent Engine
- [ ] Visible in-app Grafana panel over the Clickhouse data
- [ ] Multi-user auth for real production team use
