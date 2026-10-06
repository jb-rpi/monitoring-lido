import os
import json
import requests
import subprocess
import psutil
from datetime import datetime, UTC
from dotenv import load_dotenv

load_dotenv()

BEACON_NODE_URL = os.getenv("BEACON_NODE_URL", "http://localhost:5052")
NETHERMIND_RPC_URL = os.getenv("NETHERMIND_RPC_URL", "http://localhost:8545")
MEV_BOOST_URL = os.getenv("MEV_BOOST_URL", "http://localhost:18550")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CPU_THRESHOLD = int(os.getenv("CPU_THRESHOLD", "80"))
RAM_THRESHOLD = int(os.getenv("RAM_THRESHOLD", "85"))
DISK_THRESHOLD = int(os.getenv("DISK_THRESHOLD", "90"))
RAM_INCREASE_THRESHOLD = int(os.getenv("RAM_INCREASE_THRESHOLD", "10"))

STATE_FILE = os.path.join(os.getenv("GEMINI_TMP_DIR", "/tmp"), "health_check_state.json")


def read_state():
    """Reads the last known health state."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                state.setdefault("mev_boost_down_count", 0)
                return state
        except json.JSONDecodeError:
            pass
    return {
        "nethermind_down_count": 0,
        "lighthouse_down_count": 0,
        "mev_boost_down_count": 0,
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


def check_mev_boost():
    """Check if mev-boost is responding (at least one relay reachable)."""
    try:
        url = f"{MEV_BOOST_URL}/eth/v1/builder/status"
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Error checking mev-boost: {e}")
        return False


def get_nethermind_version():
    """Get Nethermind client version via RPC."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "web3_clientVersion",
            "params": [],
            "id": 1
        }
        response = requests.post(NETHERMIND_RPC_URL, json=payload, timeout=5)
        result = response.json().get("result", "")
        return result.split("/")[1] if "/" in result else result
    except Exception as e:
        print(f"Error getting Nethermind version: {e}")
        return "unknown"


def get_lighthouse_version():
    """Get Lighthouse client version via Beacon API."""
    try:
        url = f"{BEACON_NODE_URL}/eth/v1/node/version"
        response = requests.get(url, timeout=5)
        result = response.json().get("data", {}).get("version", "")
        return result.split("/")[1] if "/" in result else result
    except Exception as e:
        print(f"Error getting Lighthouse version: {e}")
        return "unknown"


def get_system_resources():
    """Get current CPU, RAM usage and load average."""
    cpu_percent = psutil.cpu_percent(interval=1)
    try:
        cpu_load = os.getloadavg()
    except AttributeError:
        cpu_load = (0, 0, 0)
    ram = psutil.virtual_memory()
    return cpu_percent, cpu_load, ram.percent, ram.used, ram.total


def get_uptime():
    """Get system uptime as formatted string."""
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m"


def get_disk_usage(path="/data/ethereum"):
    """Get disk usage for specified path."""
    try:
        usage = psutil.disk_usage(path)
        used_gb = usage.used / (1024**3)
        total_gb = usage.total / (1024**3)
        percent = usage.percent
        return percent, used_gb, total_gb
    except Exception as e:
        print(f"Error checking disk {path}: {e}")
        return 0, 0, 0


def make_bar(percent, length=10):
    """Render a compact progress bar, readable on mobile."""
    filled = int(length * percent / 100)
    return "█" * filled + "░" * (length - filled)


def send_discord_alert(title, status_fields, critical=False):
    """Send alert to Discord with formatted embed."""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ WARNING: DISCORD_WEBHOOK_URL not set")
        return False

    color = 15158332 if critical else 3066993

    embed = {
        "title": title,
        "color": color,
        "timestamp": datetime.now(UTC).isoformat(),
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
    cpu_percent, cpu_load, ram_percent, ram_used, ram_total = get_system_resources()
    uptime_str = get_uptime()
    disk_percent, disk_used, disk_total = get_disk_usage()

    nethermind_ok = is_process_running("nethermind") and check_nethermind_rpc()
    nethermind_version = get_nethermind_version() if nethermind_ok else "unknown"
    lighthouse_ok = is_process_running("lighthouse") and check_beacon_node()
    lighthouse_version = get_lighthouse_version() if lighthouse_ok else "unknown"
    mev_boost_ok = is_process_running("mev-boost") and check_mev_boost()

    ram_gb = ram_used / (1024**3)
    ram_total_gb = ram_total / (1024**3)
    state["ram_history"].append({"timestamp": datetime.now().isoformat(), "percent": ram_percent})
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

    if not mev_boost_ok:
        state["mev_boost_down_count"] += 1
        alerts.append({
            "name": "🚨 mev-boost",
            "value": f"DOWN ({state['mev_boost_down_count']} checks)",
            "inline": False
        })
        critical = True
    else:
        state["mev_boost_down_count"] = 0

    if cpu_percent > CPU_THRESHOLD:
        alerts.append({
            "name": "⚠️  CPU High",
            "value": f"{cpu_percent}% (seuil: {CPU_THRESHOLD}%)",
            "inline": False
        })

    if ram_percent > RAM_THRESHOLD:
        alerts.append({
            "name": "⚠️  RAM High",
            "value": f"{ram_percent}% ({ram_gb:.1f}/{ram_total_gb:.1f}GB)",
            "inline": False
        })
        critical = True

    if disk_percent > DISK_THRESHOLD:
        alerts.append({
            "name": "⚠️  Disk High",
            "value": f"{disk_percent}% ({disk_used:.0f}/{disk_total:.0f}GB)",
            "inline": False
        })
        critical = True

    if len(state["ram_history"]) > 1:
        ram_increase = state["ram_history"][-1]["percent"] - state["ram_history"][0]["percent"]
        if ram_increase > RAM_INCREASE_THRESHOLD:
            alerts.append({
                "name": "📈 RAM en hausse",
                "value": f"+{ram_increase:.1f}% sur {len(state['ram_history'])*5}min",
                "inline": False
            })

    status_fields = [
        {
            "name": "🧩 Services",
            "value": (
                f"{'✅' if nethermind_ok else '🚫'} Nethermind `{nethermind_version}`\n"
                f"{'✅' if lighthouse_ok else '🚫'} Lighthouse `{lighthouse_version}`\n"
                f"{'✅' if mev_boost_ok else '🚫'} mev-boost"
            ),
            "inline": False
        },
        {
            "name": "📊 Ressources",
            "value": (
                f"CPU   `{make_bar(cpu_percent)}` {cpu_percent}%\n"
                f"RAM   `{make_bar(ram_percent)}` {ram_gb:.1f}/{ram_total_gb:.1f}GB\n"
                f"Disk  `{make_bar(disk_percent)}` {disk_used:.0f}/{disk_total:.0f}GB"
            ),
            "inline": False
        },
        {
            "name": "ℹ️ Infos",
            "value": (
                f"Load: {cpu_load[0]:.2f} / {cpu_load[1]:.2f} / {cpu_load[2]:.2f}\n"
                f"Uptime: {uptime_str}\n"
                f"{os.uname().nodename} • {datetime.now().strftime('%H:%M:%S')}"
            ),
            "inline": False
        }
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
    print(f"✅ Health check complete - Uptime: {uptime_str}, Nethermind: {'✅' if nethermind_ok else '🚨'}, Lighthouse: {'✅' if lighthouse_ok else '🚨'}, mev-boost: {'✅' if mev_boost_ok else '🚨'}, CPU: {cpu_percent}%, RAM: {ram_percent}%, Disk: {disk_percent}%")


if __name__ == "__main__":
    main()
