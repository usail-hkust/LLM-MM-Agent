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
LLM_CONTEXT_WINDOW_TOKENS=120000
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
- Set **Context Window** in browser settings to the selected model's advertised
  input + output limit. `LLM_CONTEXT_WINDOW_TOKENS` is the server-side fallback.
- Redis is optional. Leave `REDIS_URL` empty for local single-process mode.
- `SANDBOX_TIMEOUT` controls the E2B sandbox lease in seconds. Reused sandboxes
  renew this lease automatically. E2B currently allows up to 3600 seconds on
  Hobby plans and 86400 seconds on Pro plans.

## Context Management

The demo separates durable memory from an individual model request:

- Complete workflow outputs remain in `node_versions`, and complete Copilot
  messages remain in `copilot_messages`.
- Before every OpenAI-compatible, Anthropic-compatible, Zhipu, streaming, or
  non-streaming request, the backend builds a bounded working set. It reserves
  `LLM_DEFAULT_MAX_OUTPUT_TOKENS` plus `LLM_CONTEXT_SAFETY_TOKENS`, keeps recent
  turns, and retains the beginning and end of oversized workflow prompts.
- Compaction never deletes persisted history. Older content can still be loaded
  by later requests, exported, or inspected in the UI.

The default 120,000-token window is conservative. Increase it only when the
configured model and API endpoint advertise a larger context window. Provider
prompt caching can reduce cost and latency, but it does not increase the model's
maximum context length.

## Non-Commercial Use

This demo is provided for research, evaluation, education, and other non-commercial use only.
Commercial use, resale, hosted service operation, or integration into paid products requires prior written permission from the project owner.
