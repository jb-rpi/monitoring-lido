import os
import json
import time

from common import (
    RAM_THRESHOLD, DISK_THRESHOLD,
    is_process_running, check_nethermind_rpc, check_beacon_node, check_mev_boost,
    get_system_resources, get_disk_usage, send_discord_alert,
)

SERVICE_DOWN_CHECKS = int(os.getenv("SERVICE_DOWN_CHECKS", "2"))
ALERT_REPEAT_HOURS = float(os.getenv("ALERT_REPEAT_HOURS", "6"))

STATE_FILE = os.path.join(os.getenv("GEMINI_TMP_DIR", "/tmp"), "alert_state.json")


def read_state():
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            state.setdefault("down_counts", {})
            state.setdefault("active", {})
            return state
    except (OSError, json.JSONDecodeError):
        return {"down_counts": {}, "active": {}}


def write_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def collect_problems(state):
    problems = {}

    services = {
        "Nethermind": lambda: is_process_running("nethermind") and check_nethermind_rpc(),
        "Lighthouse": lambda: is_process_running("lighthouse") and check_beacon_node(),
        "mev-boost": lambda: is_process_running("mev-boost") and check_mev_boost(),
    }
    for name, check in services.items():
        if check():
            state["down_counts"][name] = 0
        else:
            count = state["down_counts"].get(name, 0) + 1
            state["down_counts"][name] = count
            if count >= SERVICE_DOWN_CHECKS:
                problems[f"🚨 {name} DOWN"] = f"{count} checks consécutifs"

    _, _, ram_percent, ram_used, ram_total = get_system_resources()
    if ram_percent > RAM_THRESHOLD:
        problems["⚠️ RAM"] = f"{ram_percent}% ({ram_used / 1024**3:.1f}/{ram_total / 1024**3:.1f}GB)"

    disk_percent, disk_used, disk_total = get_disk_usage()
    if disk_percent > DISK_THRESHOLD:
        problems["⚠️ Disk"] = f"{disk_percent}% ({disk_used:.0f}/{disk_total:.0f}GB)"

    return problems


def main():
    state = read_state()
    problems = collect_problems(state)
    active = state["active"]
    now = time.time()
    repeat_seconds = ALERT_REPEAT_HOURS * 3600

    to_send = {k: v for k, v in problems.items() if k not in active or now - active[k] >= repeat_seconds}
    resolved = [k for k in active if k not in problems]

    if to_send:
        fields = [{"name": k, "value": v, "inline": False} for k, v in to_send.items()]
        if send_discord_alert("🚨 Critical Alert", fields, critical=True):
            for k in to_send:
                active[k] = now

    if resolved:
        fields = [{"name": k, "value": "Résolu", "inline": False} for k in resolved]
        if send_discord_alert("✅ Problème résolu", fields, critical=False):
            for k in resolved:
                del active[k]

    write_state(state)
    print(f"Alert check done - problems: {list(problems) or 'none'}")


if __name__ == "__main__":
    main()
