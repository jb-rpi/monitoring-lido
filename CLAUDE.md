# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**monitoring-lido** is a Python script that monitors the status of several Lighthouse Ethereum validators and sends grouped Discord notifications when validators go offline or come back online. The script is designed to be lightweight and cron-friendly, running periodically to check validator health.

### Key Constraints
- Python >= 3.12
- No heavy frameworks, minimal dependencies (`requests`, `python-dotenv`, `psutil`)
- Cron-friendly execution with state persistence
- No database required

## Setup & Development

### Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests python-dotenv psutil
```

### Running the Script
```bash
python src/main.py
```

### Environment Variables
Copy `.env.example` to `.env` (git-ignored) at the project root. `DISCORD_WEBHOOK_URL` is used by the health report (`health-check.py`); `ALERT_WEBHOOK_URL` is used by `alert.py` and validator alerts in `main.py` (falls back to `DISCORD_WEBHOOK_URL` if unset). `VALIDATOR_IDS` is a comma-separated list of validator indexes or public keys (legacy single `VALIDATOR_ID` is still accepted as fallback).

### Cron Integration
The script is designed for cron execution. Example entries (validators and alerts every 5 minutes, health report at 8h, 12h, 18h and 22h):
```cron
*/5 * * * * cd /home/jb/Projects/monitoring-lido && .venv/bin/python src/main.py >> monitoring.log 2>&1
*/5 * * * * cd /home/jb/Projects/monitoring-lido && .venv/bin/python src/alert.py >> monitoring.log 2>&1
0 8,12,18,22 * * * cd /home/jb/Projects/monitoring-lido && .venv/bin/python src/health-check.py >> monitoring.log 2>&1
```

## Architecture

The codebase is intentionally simple with a main script (`src/main.py`, validator monitoring; `alert.py`, `health-check.py` and `common.py` handle node/service alerts and reports) that:

1. **Status Checking**: Queries the Lighthouse Beacon Node API (`/eth/v1/beacon/states/head/validators/{id}`) to fetch validator status
2. **State Persistence**: Reads/writes validator status per-validator status (`{id: status}`) to a JSON file (`/tmp/validator_status.json` or `$GEMINI_TMP_DIR/validator_status.json`) to detect state changes across cron runs
3. **State Change Detection**: Compares current status with last known status to determine if validator went online/offline
4. **Notifications**: Sends one grouped Discord webhook message per run, only for state transitions (online → offline or offline → online), avoiding spam
5. **Error Handling**: Gracefully handles network errors, timeouts, and API issues with detailed logging

### Key Functions
- `check_validator_status()`: Queries Beacon Node API with error handling
- `check_performance()`: Checks slashing, balance trend and attestation liveness
- `read_all_status()` / `write_all_status()`: Manages per-validator persistent state across runs
- `send_discord_message()`: Posts to Discord webhook with error recovery
- `main()`: Loops over `VALIDATOR_IDS`, then sends grouped notifications

## Important Notes for Development

- **Stateless Between Runs**: The script relies on the status JSON file to detect state changes. This is critical for cron execution where each run is independent.
- **State File Location**: Uses `GEMINI_TMP_DIR` environment variable (falling back to `/tmp`) for the status file. This supports various execution environments.
- **Validation ID Flexibility**: Accepts both validator public key and validator index for flexibility.
- **No Spam Logic**: Discord messages are only sent on state transitions, not on every check. If offline, subsequent checks don't resend the alert.

## LLM Operating Rules

These rules from `llm-rules.md` apply to this project:
- Respond with the minimum necessary
- No theoretical recalls
- No question reformulations
- Code only if asked
- No unnecessary comments in code
- Use diffs or targeted excerpts

Additional context from `llm-context.md`:
- Goal: Monitor that Nethermind/Lighthouse nodes work correctly and handle maintenance reboots
- Constraints: Python >3.12, no heavy frameworks, cron-friendly
- Current state: Single script in `src/`, console + Discord output
- Do NOT assume: database, proprietary APIs
