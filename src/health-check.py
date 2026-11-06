import os
from datetime import datetime

from common import (
    CPU_THRESHOLD, RAM_THRESHOLD, DISK_THRESHOLD,
    is_process_running, check_nethermind_rpc, check_beacon_node, check_mev_boost,
    get_nethermind_version, get_lighthouse_version, get_mev_boost_version,
    get_system_resources, get_uptime, get_disk_usage, make_bar, send_discord_alert,
)


def main():
    cpu_percent, cpu_load, ram_percent, ram_used, ram_total = get_system_resources()
    uptime_str = get_uptime()
    disk_percent, disk_used, disk_total = get_disk_usage()

    nethermind_ok = is_process_running("nethermind") and check_nethermind_rpc()
    nethermind_version = get_nethermind_version() if nethermind_ok else "unknown"
    lighthouse_ok = is_process_running("lighthouse") and check_beacon_node()
    lighthouse_version = get_lighthouse_version() if lighthouse_ok else "unknown"
    mev_boost_ok = is_process_running("mev-boost") and check_mev_boost()
    mev_boost_version = get_mev_boost_version() if mev_boost_ok else "unknown"

    ram_gb = ram_used / (1024**3)
    ram_total_gb = ram_total / (1024**3)

    alerts = []
    critical = False

    for name, ok in (("Nethermind", nethermind_ok), ("Lighthouse", lighthouse_ok), ("mev-boost", mev_boost_ok)):
        if not ok:
            alerts.append({"name": f"🚨 {name}", "value": "DOWN", "inline": False})
            critical = True

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

    status_fields = [
        {
            "name": "🧩 Services",
            "value": (
                f"{'✅' if nethermind_ok else '🚫'} Nethermind `{nethermind_version}`\n"
                f"{'✅' if lighthouse_ok else '🚫'} Lighthouse `{lighthouse_version}`\n"
                f"{'✅' if mev_boost_ok else '🚫'} mev-boost `{mev_boost_version}`"
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
        title = "🚨 Critical Status Report" if critical else "🔔 Status Report"
    else:
        status_fields.append({"name": "Status", "value": "✨ All systems nominal", "inline": False})
        title = "✅ Node Health Check"

    send_discord_alert(title, status_fields, critical=critical)
    print(f"Health report sent - Uptime: {uptime_str}, Nethermind: {nethermind_ok}, Lighthouse: {lighthouse_ok}, mev-boost: {mev_boost_ok}, CPU: {cpu_percent}%, RAM: {ram_percent}%, Disk: {disk_percent}%")


if __name__ == "__main__":
    main()
