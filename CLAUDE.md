# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Edict (三省六部)** is an AI multi-agent orchestration framework modeled on ancient Chinese imperial governance. Agents are organized into institutional roles (太子, 中书省, 门下省, 尚书省, 六部) with mandatory review gates, strict state machines, and complete auditability via event sourcing.

## Commands

### Backend
```bash
cd edict/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Run Alembic migrations
alembic upgrade head

# Run orchestrator worker standalone
python -m app.workers.orchestrator_worker
```

### Frontend
```bash
cd edict/frontend
npm install
npm run dev        # dev server (run manually)
npm run build
npm run preview
```

### Docker
```bash
docker-compose up -d          # root docker-compose.yml (demo image)
docker-compose -f edict/docker-compose.yml up -d  # full stack
```

## Architecture

### Data Flow
```
User → task.created (Redis Stream)
     → OrchestratorWorker consumes
     → dispatches to taizi agent via task.dispatch
     → agent completes → task.status event
     → Orchestrator routes to next agent per STATE_AGENT_MAP
     → ... pipeline continues to Done
```

### Backend (`edict/backend/app/`)

- **`models/task.py`** — `Task` ORM, `TaskState` enum, `STATE_TRANSITIONS` dict (legal state flows), `STATE_AGENT_MAP` (state→agent routing), `ORG_AGENT_MAP` (六部 routing)
- **`services/event_bus.py`** — Redis Streams wrapper; 14 topic constants (`TOPIC_TASK_CREATED`, `TOPIC_TASK_STATUS`, etc.); consumer groups with ACK for guaranteed delivery
- **`services/task_service.py`** — All business logic: `create_task()`, `transition_state()` (validates against `STATE_TRANSITIONS`), `request_dispatch()`, `add_progress()`, `update_todos()`
- **`workers/orchestrator_worker.py`** — Consumes Redis events, drives state machine, auto-dispatches to next agent. Recovers crashed events via `claim_stale()`
- **`api/`** — FastAPI routers: `tasks`, `agents`, `events`, `admin`, `websocket`, `legacy`
- **`config.py`** — All settings from env vars (Postgres, Redis, OpenClaw URLs)

### Frontend (`edict/frontend/src/`)

- **`store.ts`** — Zustand store; polls `/api/live-status` every 5s; manages 9 tabs
- **`api.ts`** — HTTP client to backend
- **`App.tsx`** — Tab shell routing to 9 panels
- Components map 1:1 to tabs: `EdictBoard` (kanban), `MonitorPanel`, `OfficialPanel`, `ModelConfig`, `SkillsConfig`, `SessionsPanel`, `MemorialPanel`, `TemplatePanel`, `MorningPanel`

### State Machine (三省六部制)
```
Taizi → Zhongshu → Menxia → Assigned → Doing → Review → Done
                 ↑_______↓ (封驳退回)          ↑____↓ (审查退回)
```
Terminal states: `Done`, `Cancelled`. Blocked tasks can resume to any non-terminal state.

### Event Topics (Redis Streams)
14 topics defined as constants in `event_bus.py`. Key ones:
- `task.created` → triggers Taizi dispatch
- `task.status` → triggers next-agent routing
- `task.dispatch` → consumed by OpenClaw agent runtime
- `task.stalled` → triggers intervention logic

### Agent Definitions
Each agent has `agents/<name>/SOUL.md` defining role, workflow, and output format. Six ministries (六部) are execution-layer agents reused across governance models.

## Key Design Constraints

- `state` field in `Task` is a PostgreSQL Enum type — changing states requires an Alembic migration
- `STATE_TRANSITIONS` in `task.py` is the single source of truth for legal state flows; `transition_state()` in `task_service.py` enforces it
- OrchestratorWorker does NOT ACK failed events — they get redelivered automatically
- Frontend uses 5s polling (no WebSocket for main data); WebSocket exists at `/ws` for push notifications
- Default governance is `san_sheng` (三省六部制); all new governance models must be backward-compatible

## Environment Variables (`.env`)
```
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
REDIS_URL
OPENCLAW_GATEWAY_URL, OPENCLAW_BIN, OPENCLAW_PROJECT_DIR
STALL_THRESHOLD_SEC, MAX_DISPATCH_RETRY, DISPATCH_TIMEOUT_SEC
FEISHU_DELIVER, FEISHU_CHANNEL
```

## Current State (as of 2026-03-15)

The governance multi-model expansion (9 governance types + 3 cross-cutting mechanisms) was implemented and then reverted. The `governance/` package, related DB migration, API endpoints, and frontend `GovernancePanel` are all deleted in the working tree. The `plan.md` documents the full design — it is the authoritative spec for re-implementing this feature.
