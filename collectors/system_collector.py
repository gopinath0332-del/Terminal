"""
collectors/system_collector.py
==============================
Collects hardware telemetry (CPU, RAM, Temp) and systemd service health
on Raspberry Pi production server with graceful fallbacks for local dev.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None

from collectors.base import ServiceHealth, SystemMetrics

logger = logging.getLogger(__name__)


class SystemCollector:
    """Gathers OS metrics and systemd service states."""

    def __init__(self, services: Dict[str, str]):
        self.services = services
        self._has_systemctl = shutil.which("systemctl") is not None

    def get_metrics(self) -> SystemMetrics:
        """Fetch CPU, RAM, Disk, and CPU Temperature."""
        if psutil is None:
            return SystemMetrics(temperature_c=self._read_pi_temperature())

        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/") if os.path.exists("/") else psutil.disk_usage("C:\\")

            temp = self._read_pi_temperature()

            return SystemMetrics(
                cpu_percent=cpu,
                ram_percent=mem.percent,
                ram_used_gb=round(mem.used / (1024 ** 3), 2),
                ram_total_gb=round(mem.total / (1024 ** 3), 2),
                disk_percent=disk.percent,
                temperature_c=temp,
            )
        except Exception as e:
            logger.warning(f"Error reading system metrics: {e}")
            return SystemMetrics()

    def get_service_status(self, service_unit: str) -> ServiceHealth:
        """Check status of a systemd unit (service or timer)."""
        if not self._has_systemctl:
            # Running on local dev (e.g. Windows)
            return ServiceHealth(
                name=service_unit,
                status="dev_mode",
                sub_state="local",
                uptime="N/A (Dev)",
                description="Dev Environment (No systemd)",
            )

        try:
            # Fast check with systemctl is-active
            res = subprocess.run(
                ["systemctl", "is-active", service_unit],
                capture_output=True,
                text=True,
                timeout=3,
            )
            raw_state = res.stdout.strip().lower()

            # Detailed property lookup for uptime/substate
            prop_res = subprocess.run(
                ["systemctl", "show", service_unit, "--property=ActiveState,SubState,ActiveEnterTimestamp"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            props: Dict[str, str] = {}
            for line in prop_res.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()

            active_state = props.get("ActiveState", raw_state)
            sub_state = props.get("SubState", "")
            enter_ts = props.get("ActiveEnterTimestamp", "")

            # Normalize status
            status = active_state
            if active_state == "active":
                status = "active"
            elif active_state in ("inactive", "failed"):
                status = active_state
            elif "waiting" in sub_state or service_unit.endswith(".timer"):
                status = "waiting"

            return ServiceHealth(
                name=service_unit,
                status=status,
                sub_state=sub_state,
                uptime=enter_ts if enter_ts else "active",
            )
        except Exception as e:
            logger.error(f"Failed to query systemctl for {service_unit}: {e}")
            return ServiceHealth(name=service_unit, status="unknown", description=str(e))

    def _read_pi_temperature(self) -> Optional[float]:
        """Read Raspberry Pi SoC temperature."""
        # 1. Standard Linux thermal zone
        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(thermal_path):
            try:
                with open(thermal_path, "r") as f:
                    content = f.read().strip()
                    return round(float(content) / 1000.0, 1)
            except Exception:
                pass

        # 2. Raspberry Pi vcgencmd utility
        vcgencmd = shutil.which("vcgencmd")
        if vcgencmd:
            try:
                out = subprocess.check_output([vcgencmd, "measure_temp"], text=True, timeout=2)
                # Format: temp=43.5'C
                if "temp=" in out:
                    val = out.replace("temp=", "").replace("'C", "").strip()
                    return float(val)
            except Exception:
                pass

        return None
