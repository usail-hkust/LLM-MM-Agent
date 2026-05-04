# MM-Agent Demo

## Requirements

- Python 3.10+
- Node.js 20+
- npm
- LLM API key
- E2B API key for sandbox execution. Sign in or register at https://e2b.dev/ to create one.

## Quick Start

From the repository root:

```bash
cp demo/.env.example demo/.env
cp demo/frontend/.env.local.example demo/frontend/.env.local
```

Edit `demo/.env`:

```env
API_KEY=your_llm_key
BASE_URL=https://api.minimaxi.com/anthropic
MODEL_NAME=MiniMax-M2.7-highspeed
AGENT_MODEL_NAME=MiniMax-M2.7-highspeed
E2B_API_KEY=your_e2b_key
```

Start the demo:

```bash
bash demo/scripts/run.sh
```

Open:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

Default login:

```text
admin@local.dev
admin12345
```

## Commands

```bash
bash demo/scripts/run.sh       # install dependencies, build, and start
bash demo/scripts/status.sh    # show backend/frontend status
bash demo/scripts/stop.sh      # stop backend/frontend
bash demo/scripts/clean.sh     # remove generated runtime/build files
bash demo/scripts/clean.sh --all  # also remove backend/.venv and frontend/node_modules
```

Development mode:

```bash
FRONTEND_MODE=dev bash demo/scripts/run.sh
```

## Dependency Files

- Backend Python dependencies: `demo/requirements.txt`
- Frontend dependencies: `demo/frontend/package.json`
- Frontend lockfile: `demo/frontend/package-lock.json`

## Notes

- SQLite data and uploaded files are stored under `demo/runtime/` and `demo/backend/runtime/`.
- Browser settings can override LLM/E2B keys through `X-LLM-*` and `X-E2B-API-Key` headers.
- Redis is optional. Leave `REDIS_URL` empty for local single-process mode.

## Non-Commercial Use

This demo is provided for research, evaluation, education, and other non-commercial use only.
Commercial use, resale, hosted service operation, or integration into paid products requires prior written permission from the project owner.
