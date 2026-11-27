"""Tests for the system_devices tool."""

from __future__ import annotations

import pytest

from apex.tools import system_devices as devices


@pytest.fixture()
def tool():
    return devices.SystemDevicesTool()


def test_unknown_query_lists_valid_queries(tool):
    result = tool.execute(query="toaster")

    assert not result.success
    assert "printers" in result.content
    assert "bluetooth" in result.content


def test_summary_reports_the_operating_system(tool):
    result = tool.execute(query="summary")

    assert result.success
    assert "OS:" in result.content
    assert "Host:" in result.content


def test_printers_query_uses_the_platform_command(tool, monkeypatch):
    calls = []

    def fake_run(command, timeout=30):
        calls.append(command)
        return True, "Name   PrinterStatus\n----   -------------\nHP     Normal"

    monkeypatch.setattr(devices, "_run_command", fake_run)
    monkeypatch.setattr(devices.sys, "platform", "win32")

    result = tool.execute(query="printers")

    assert result.success
    assert "HP     Normal" in result.content
    assert any("Get-Printer" in str(call) for call in calls)


def test_bluetooth_query_reports_devices(tool, monkeypatch):
    def fake_run(command, timeout=30):
        return True, "Status  FriendlyName\n------  ------------\nOK      Headphones"

    monkeypatch.setattr(devices, "_run_command", fake_run)
    monkeypatch.setattr(devices.sys, "platform", "win32")

    result = tool.execute(query="bluetooth")

    assert result.success
    assert "Headphones" in result.content


def test_failed_command_is_reported_as_failure(tool, monkeypatch):
    monkeypatch.setattr(
        devices,
        "_run_command",
        lambda command, timeout=30: (False, "Command not available on this system"),
    )
    monkeypatch.setattr(devices.sys, "platform", "linux")

    result = tool.execute(query="usb")

    assert not result.success
    assert "not available" in result.content


def test_spec_declares_system_capability(tool):
    spec = tool.spec

    assert spec.name == "system_devices"
    assert spec.category == "system"
    assert "system:admin" in spec.required_capabilities
    assert "printers" in spec.parameters["properties"]["query"]["enum"]
