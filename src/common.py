import os
import requests
import subprocess
import psutil
from datetime import datetime, UTC
from dotenv import load_dotenv

load_dotenv()

BEACON_NODE_URL = os.getenv("BEACON_NODE_URL", "http://localhost:5052")
NETHERMIND_RPC_URL = os.getenv("NETHERMIND_RPC_URL", "http://localhost:8545")
MEV_BOOST_URL = os.getenv("MEV_BOOST_URL", "http://localhost:18550")
MEV_BOOST_BIN = os.getenv("MEV_BOOST_BIN", "mev-boost")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CPU_THRESHOLD = int(os.getenv("CPU_THRESHOLD", "80"))
RAM_THRESHOLD = int(os.getenv("RAM_THRESHOLD", "85"))
DISK_THRESHOLD = int(os.getenv("DISK_THRESHOLD", "90"))


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


def get_mev_boost_version():
    """Get mev-boost version via its CLI --version flag."""
    try:
        result = subprocess.run(
            [MEV_BOOST_BIN, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = (result.stdout or result.stderr).strip()
        return output.split()[-1] if output else "unknown"
    except Exception as e:
        print(f"Error getting mev-boost version: {e}")
        return "unknown"


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
