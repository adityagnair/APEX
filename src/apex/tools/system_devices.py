"""System devices tool — inspect the machine and its attached hardware.

A read-only inventory of the host: operating system and resources, printers
and queued print jobs, Bluetooth and USB devices, audio devices, network
adapters, disks, displays and battery.  Windows is queried through PowerShell,
macOS through ``system_profiler``/``lpstat``/``pmset``, Linux through
``lpstat``/``bluetoothctl``/``lsusb``/``ip``.

Nothing here changes system state: every query only reports what exists.
"""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Tuple

from apex.core.registry import ToolRegistry
from apex.core.types import ToolResult
from apex.tools._stubs import BaseTool, ToolSpec

_MAX_OUTPUT_CHARS = 20_000
_DEFAULT_TIMEOUT = 30

_QUERIES = (
    "summary",
    "printers",
    "print_jobs",
    "bluetooth",
    "usb",
    "audio",
    "network",
    "disks",
    "displays",
    "battery",
)

# Child processes need the platform's bootstrap variables; everything else in
# the parent environment (tokens, API keys) is deliberately withheld.
_ENV_KEYS = (
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "TERM",
    "SystemRoot",
    "SystemDrive",
    "windir",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "ProgramFiles",
)


def _child_env() -> Dict[str, str]:
    return {key: os.environ[key] for key in _ENV_KEYS if key in os.environ}


def _run_command(
    command: List[str], timeout: int = _DEFAULT_TIMEOUT
) -> Tuple[bool, str]:
    """Run a read-only inspection command and return ``(ok, text)``."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_child_env(),
            errors="replace",
        )
    except FileNotFoundError:
        return False, f"Command not available on this system: {command[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s: {command[0]}"
    except OSError as exc:
        return False, f"Could not run {command[0]}: {exc}"
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if stdout:
        return completed.returncode == 0, stdout
    return completed.returncode == 0, stderr


def _powershell(script: str, timeout: int = _DEFAULT_TIMEOUT) -> Tuple[bool, str]:
    executable = shutil.which("powershell") or "powershell"
    return _run_command(
        [
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        timeout=timeout,
    )


def _first_success(attempts: List[Tuple[str, List[str]]]) -> Tuple[bool, str]:
    """Try commands in order and return the first one that produced output."""
    last: Tuple[bool, str] = (False, "No inspection command available.")
    for label, command in attempts:
        ok, text = _run_command(command)
        if ok and text:
            return True, f"{label}:\n{text}"
        if text:
            last = (ok, f"{label}:\n{text}")
    return last


@ToolRegistry.register("system_devices")
class SystemDevicesTool(BaseTool):
    """Report the host's operating system, devices and attached hardware."""

    tool_id = "system_devices"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="system_devices",
            description=(
                "Inspect this computer and the devices connected to it. Queries: "
                "'summary' (OS, CPU, memory, disk space), 'printers', "
                "'print_jobs' (queued print jobs), 'bluetooth', 'usb', 'audio', "
                "'network', 'disks', 'displays', 'battery'. Read-only."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "enum": list(_QUERIES),
                        "description": "Which device inventory to report.",
                    }
                },
                "required": ["query"],
            },
            category="system",
            timeout_seconds=60.0,
            required_capabilities=["system:admin"],
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def execute(self, **params: Any) -> ToolResult:
        query = str(params.get("query", "") or "").strip().lower().replace("-", "_")
        if query not in _QUERIES:
            return ToolResult(
                tool_name="system_devices",
                content=(
                    f"Unknown query {query!r}. "
                    f"Valid queries: {', '.join(_QUERIES)}."
                ),
                success=False,
            )
        handler = getattr(self, f"_query_{query}")
        try:
            ok, text = handler()
        except Exception as exc:  # pragma: no cover - defensive
            return ToolResult(
                tool_name="system_devices",
                content=f"{query} query failed: {exc}",
                success=False,
                metadata={"query": query},
            )
        text = text.strip() or "(no devices reported)"
        if len(text) > _MAX_OUTPUT_CHARS:
            text = text[:_MAX_OUTPUT_CHARS] + "\n... (output truncated)"
        return ToolResult(
            tool_name="system_devices",
            content=f"{query} on {platform.system()}:\n{text}",
            success=ok,
            metadata={"query": query, "platform": sys.platform},
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _query_summary(self) -> Tuple[bool, str]:
        lines = [
            f"Host:         {platform.node()}",
            f"OS:           {platform.system()} {platform.release()}"
            f" ({platform.version()})",
            f"Architecture: {platform.machine()}",
        ]
        processor = (platform.processor() or "").strip()
        cores = os.cpu_count() or 0
        if processor:
            lines.append(f"CPU:          {processor} ({cores} logical cores)")
        elif cores:
            lines.append(f"CPU:          {cores} logical cores")
        try:
            import psutil

            memory = psutil.virtual_memory()
            lines.append(
                f"Memory:       {_gb(memory.used)} used of {_gb(memory.total)}"
                f" ({memory.percent:.0f}% used)"
            )
            boot = psutil.boot_time()
            import time

            lines.append(
                "Uptime:       "
                f"{_duration(time.time() - boot)} (since"
                f" {time.strftime('%Y-%m-%d %H:%M', time.localtime(boot))})"
            )
        except Exception:
            pass
        try:
            usage = shutil.disk_usage(os.path.expanduser("~"))
            lines.append(
                f"Home disk:    {_gb(usage.used)} used of {_gb(usage.total)}"
                f" ({_gb(usage.free)} free)"
            )
        except OSError:
            pass
        lines.append(f"PowerShell:   {'yes' if _has_powershell() else 'no'}")
        return True, "\n".join(lines)

    def _query_printers(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-Printer | Select-Object Name, DriverName, PortName,"
                " PrinterStatus, Shared | Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _first_success(
                [
                    ("Installed printers", ["lpstat", "-p", "-d"]),
                    ("Printer hardware", ["system_profiler", "SPPrintersDataType"]),
                ]
            )
        return _first_success(
            [
                ("Installed printers", ["lpstat", "-p", "-d"]),
                ("CUPS printers", ["ls", "/etc/cups/printers.conf"]),
            ]
        )

    def _query_print_jobs(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-Printer | ForEach-Object { Get-PrintJob -PrinterName"
                " $_.Name -ErrorAction SilentlyContinue } | Select-Object"
                " PrinterName, DocumentName, JobStatus, SubmittedTime |"
                " Format-Table -AutoSize"
            )
        return _run_command(["lpstat", "-o"])

    def _query_bluetooth(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-PnpDevice -Class Bluetooth | Select-Object Status,"
                " FriendlyName, InstanceId | Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _run_command(
                ["system_profiler", "SPBluetoothDataType"], timeout=45
            )
        return _first_success(
            [
                ("Paired/known Bluetooth devices", ["bluetoothctl", "devices"]),
                ("Bluetooth adapter", ["bluetoothctl", "show"]),
                ("Bluetooth service", ["systemctl", "status", "bluetooth"]),
            ]
        )

    def _query_usb(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like"
                " 'USB*' } | Select-Object Status, Class, FriendlyName |"
                " Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _run_command(["system_profiler", "SPUSBDataType"], timeout=45)
        return _first_success(
            [
                ("USB devices", ["lsusb"]),
                ("USB devices (sysfs)", ["ls", "/sys/bus/usb/devices"]),
            ]
        )

    def _query_audio(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-CimInstance Win32_SoundDevice | Select-Object Name,"
                " Manufacturer, Status | Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _run_command(["system_profiler", "SPAudioDataType"], timeout=45)
        return _first_success(
            [
                ("Audio sinks", ["pactl", "list", "short", "sinks"]),
                ("Audio devices", ["aplay", "-l"]),
            ]
        )

    def _query_network(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-NetAdapter | Select-Object Name, InterfaceDescription,"
                " Status, LinkSpeed | Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _run_command(["networksetup", "-listallhardwareports"])
        return _first_success(
            [
                ("Network interfaces", ["ip", "-brief", "address"]),
                ("Network interfaces", ["ifconfig", "-a"]),
            ]
        )

    def _query_disks(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,"
                " VolumeName, FileSystem,"
                " @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}},"
                " @{n='FreeGB';e={[math]::Round($_.FreeSpace/1GB,1)}} |"
                " Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _run_command(["df", "-h"])
        return _first_success(
            [
                ("Mounted filesystems", ["df", "-h"]),
                ("Block devices", ["lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT"]),
            ]
        )

    def _query_displays(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-CimInstance Win32_VideoController | Select-Object Name,"
                " DriverVersion, CurrentHorizontalResolution,"
                " CurrentVerticalResolution | Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _run_command(["system_profiler", "SPDisplaysDataType"], timeout=45)
        return _first_success(
            [
                ("Monitors", ["xrandr", "--listmonitors"]),
                ("Displays", ["xrandr", "--query"]),
            ]
        )

    def _query_battery(self) -> Tuple[bool, str]:
        if sys.platform == "win32":
            return _powershell(
                "Get-CimInstance Win32_Battery | Select-Object Name,"
                " EstimatedChargeRemaining, BatteryStatus | Format-Table -AutoSize"
            )
        if sys.platform == "darwin":
            return _run_command(["pmset", "-g", "batt"])
        capacities = sorted(glob.glob("/sys/class/power_supply/BAT*/capacity"))
        if capacities:
            lines: List[str] = []
            for capacity_file in capacities:
                name = os.path.basename(os.path.dirname(capacity_file))
                try:
                    with open(capacity_file, encoding="utf-8") as handle:
                        percent = handle.read().strip()
                except OSError:
                    continue
                status_path = os.path.join(
                    os.path.dirname(capacity_file), "status"
                )
                status = ""
                try:
                    with open(status_path, encoding="utf-8") as handle:
                        status = handle.read().strip()
                except OSError:
                    pass
                lines.append(f"{name}: {percent}% {status}".rstrip())
            if lines:
                return True, "\n".join(lines)
        return _first_success(
            [
                ("Battery", ["upower", "-e"]),
                ("ACPI", ["acpi", "-b"]),
            ]
        )


def _has_powershell() -> bool:
    return shutil.which("powershell") is not None or shutil.which("pwsh") is not None


def _gb(value: float) -> str:
    return f"{value / (1024**3):.1f} GB"


def _duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


__all__ = ["SystemDevicesTool"]
