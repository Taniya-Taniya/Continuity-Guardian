# Architecture

```
                 WEB APP (frontend/)
     Producer Dashboard | Upload Portal | Reports
                        |
                 ORCHESTRATOR (agents/orchestrator)
   Routes tasks to agents, enforces forced-check rule,
        maintains project state
   /   |    |     |      |      |      |     \
Script Cont Perf Budget Previz Score  Local  Access
Agent  Agent Agent Agent Agent  Agent  Agent  Agent
   \   |    |     |      |      |      |     /
        DATA LAYER (Cloud Storage + BigQuery + Vertex AI Search)
                        |
        Grafana / Clickhouse — live analytics dashboard
```

## Forced-check rule

`orchestrator.lock_scene()` refuses to mark a scene "locked" unless
both `continuity_check` and `budget_check` have run for the scene's
current takes in this session. The frontend mirrors this same rule
client-side (see `renderLockControl()` in `frontend/js/app.js`) so
the UI never shows a lockable scene that the backend would reject —
but the backend check is the real guard; never trust the client-side
copy alone once this is wired to the real API.

## Agent → data flow

Each agent is a pure function over `Scene` (see `docs/schema.md`):
read the fields it needs, write the fields it owns, leave everything
else untouched. This keeps agents independently testable and lets
different teammates own different agents without merge conflicts.
