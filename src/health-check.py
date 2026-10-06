import os
import json
import requests
import subprocess
import psutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BEACON_NODE_URL = os.getenv("BEACON_NODE_URL", "http://localhost:5052")
NETHERMIND_RPC_URL = os.getenv("NETHERMIND_RPC_URL", "http://localhost:8545")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CPU_THRESHOLD = int(os.getenv("CPU_THRESHOLD", "80"))
RAM_THRESHOLD = int(os.getenv("RAM_THRESHOLD", "85"))
RAM_INCREASE_THRESHOLD = int(os.getenv("RAM_INCREASE_THRESHOLD", "10"))

STATE_FILE = os.path.join(os.getenv("GEMINI_TMP_DIR", "/tmp"), "health_check_state.json")


def read_state():
    """Reads the last known health state."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {
        "nethermind_down_count": 0,
        "lighthouse_down_count": 0,
        "rpc_down_count": 0,
        "last_alert_sent": None,
        "ram_history": []
    }


def write_state(state):
    """Writes the current health state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def is_process_running(process_name):
    """Check if a process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking process {process_name}: {e}")
        return False


def check_nethermind_rpc():
    """Check if Nethermind RPC is responding."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }
        response = requests.post(
            NETHERMIND_RPC_URL,
            json=payload,
            timeout=5
        )
        return response.status_code == 200 and "result" in response.json()
    except Exception as e:
        print(f"Error checking Nethermind RPC: {e}")
        return False


def check_beacon_node():
    """Check if Lighthouse Beacon Node is responding."""
    try:
        url = f"{BEACON_NODE_URL}/eth/v1/node/health"
        response = requests.get(url, timeout=5)
        return response.status_code in [200, 206]
    except Exception as e:
        print(f"Error checking Beacon Node: {e}")
        return False


def get_system_resources():
    """Get current CPU and RAM usage."""
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    return cpu_percent, ram.percent, ram.used, ram.total


def send_discord_alert(title, status_fields, critical=False):
    """Send alert to Discord with formatted embed."""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ WARNING: DISCORD_WEBHOOK_URL not set")
        return False

    color = 15158332 if critical else 3066993  # Red if critical, Green otherwise

    embed = {
        "title": title,
        "color": color,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "fields": status_fields,
        "footer": {"text": "🖥️  Node Health Monitor"}
    }

    payload = {"embeds": [embed]}

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Discord notification sent")
        return True
    except Exception as e:
        print(f"❌ Error sending Discord notification: {e}")
        return False


def main():
    state = read_state()
    cpu, ram, ram_used, ram_total = get_system_resources()

    nethermind_ok = is_process_running("nethermind") and check_nethermind_rpc()
    lighthouse_ok = is_process_running("lighthouse") and check_beacon_node()

    ram_gb = ram_used / (1024**3)
    ram_total_gb = ram_total / (1024**3)
    state["ram_history"].append({"timestamp": datetime.now().isoformat(), "percent": ram})
    state["ram_history"] = state["ram_history"][-288:]

    alerts = []
    critical = False

    if not nethermind_ok:
        state["nethermind_down_count"] += 1
        alerts.append({
            "name": "🚨 Nethermind",
            "value": f"DOWN ({state['nethermind_down_count']} checks)",
            "inline": False
        })
        critical = True
    else:
        state["nethermind_down_count"] = 0

    if not lighthouse_ok:
        state["lighthouse_down_count"] += 1
        alerts.append({
            "name": "🚨 Lighthouse",
            "value": f"DOWN ({state['lighthouse_down_count']} checks)",
            "inline": False
        })
        critical = True
    else:
        state["lighthouse_down_count"] = 0

    if cpu > CPU_THRESHOLD:
        alerts.append({
            "name": "⚠️  CPU High",
            "value": f"{cpu}% (threshold: {CPU_THRESHOLD}%)",
            "inline": True
        })

    if ram > RAM_THRESHOLD:
        alerts.append({
            "name": "⚠️  RAM High",
            "value": f"{ram}% ({ram_gb:.1f}GB / {ram_total_gb:.1f}GB)",
            "inline": True
        })
        critical = True

    if len(state["ram_history"]) > 1:
        ram_increase = state["ram_history"][-1]["percent"] - state["ram_history"][0]["percent"]
        if ram_increase > RAM_INCREASE_THRESHOLD:
            alerts.append({
                "name": "📈 RAM Increasing",
                "value": f"+{ram_increase:.1f}% over {len(state['ram_history'])*5}min",
                "inline": True
            })

    status_fields = [
        {"name": "Nethermind", "value": "✅ Online" if nethermind_ok else "🚫 Offline", "inline": True},
        {"name": "Lighthouse", "value": "✅ Online" if lighthouse_ok else "🚫 Offline", "inline": True},
        {"name": "CPU Usage", "value": f"📊 {cpu}%", "inline": True},
        {"name": "RAM Usage", "value": f"💾 {ram}% ({ram_gb:.1f}GB)", "inline": True},
        {"name": "Timestamp", "value": f"🕐 {datetime.now().strftime('%H:%M:%S')}", "inline": True},
        {"name": "Hostname", "value": f"🖥️  {os.uname().nodename}", "inline": True}
    ]

    if alerts:
        status_fields.extend(alerts)
        send_discord_alert(
            "🔔 Node Health Alert" if not critical else "🚨 Critical Alert",
            status_fields,
            critical=critical
        )
    else:
        status_fields.append({
            "name": "Status",
            "value": "✨ All systems nominal",
            "inline": False
        })
        send_discord_alert(
            "✅ Node Health Check",
            status_fields,
            critical=False
        )

    write_state(state)
    print(f"✅ Health check complete - Nethermind: {'✅' if nethermind_ok else '🚨'}, Lighthouse: {'✅' if lighthouse_ok else '🚨'}, CPU: {cpu}%, RAM: {ram}%")


if __name__ == "__main__":
    main()
