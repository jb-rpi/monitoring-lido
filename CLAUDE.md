# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**monitoring-lido** is a Python script that monitors the status of a Lighthouse Ethereum validator and sends Discord notifications when the validator goes offline or comes back online. The script is designed to be lightweight and cron-friendly, running periodically to check validator health.

### Key Constraints
- Python >= 3.12
- No heavy frameworks, minimal dependencies (only `requests`)
- Cron-friendly execution with state persistence
- No database required

## Setup & Development

### Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests
```

### Running the Script
```bash
python src/main.py
```

### Environment Variables
Configure a `.env` file at the project root:
```env
BEACON_NODE_URL=http://localhost:5052
VALIDATOR_ID=YOUR_VALIDATOR_ID_OR_PUBLIC_KEY
DISCORD_WEBHOOK_URL=YOUR_DISCORD_WEBHOOK_URL
```

### Cron Integration
The script is designed for cron execution. Example entry to run every 5 minutes:
```cron
*/5 * * * * cd /home/jb/Projects/monitoring-lido && source .venv/bin/activate && python src/main.py >> /var/log/monitoring-lido.log 2>&1
```

## Architecture

The codebase is intentionally simple with a single script (`src/main.py`) that:

1. **Status Checking**: Queries the Lighthouse Beacon Node API (`/eth/v1/beacon/states/head/validators/{id}`) to fetch validator status
2. **State Persistence**: Reads/writes validator status to a JSON file (`/tmp/validator_status.json` or `$GEMINI_TMP_DIR/validator_status.json`) to detect state changes across cron runs
3. **State Change Detection**: Compares current status with last known status to determine if validator went online/offline
4. **Notifications**: Sends Discord webhook notifications only on state transitions (online → offline or offline → online), avoiding spam
5. **Error Handling**: Gracefully handles network errors, timeouts, and API issues with detailed logging

### Key Functions
- `check_validator_status()`: Queries Beacon Node API with error handling
- `read_last_status()` / `write_current_status()`: Manages persistent state across runs
- `send_discord_message()`: Posts to Discord webhook with error recovery
- `main()`: Orchestrates the monitoring flow

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
