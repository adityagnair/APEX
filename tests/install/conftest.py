"""Test fixtures for installer / cold-start refresh tests."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def tmp_apex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``DEFAULT_CONFIG_DIR`` at a tmpdir for isolated tests.

    Returns the directory; teardown is automatic via tmp_path.
    """
    home = tmp_path / ".apex"
    home.mkdir()
    (home / ".state").mkdir()
    (home / ".state" / "models").mkdir()
    (home / ".scripts").mkdir()
    config_path = home / "config.toml"
    monkeypatch.setattr("apex.core.config.DEFAULT_CONFIG_DIR", home)
    monkeypatch.setattr("apex.core.config.DEFAULT_CONFIG_PATH", config_path)
    # Also patch init_cmd's module-level bindings (imported with ``from ... import``).
    monkeypatch.setattr("apex.cli.init_cmd.DEFAULT_CONFIG_DIR", home)
    monkeypatch.setattr("apex.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path)
    # Patch doctor_cmd's module-level bindings.
    monkeypatch.setattr("apex.cli.doctor_cmd.DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    # These tests drive state purely via marker files; pin the runtime Rust
    # import check off so a built extension in the dev venv can't flip
    # "pending"/"failed" to "ready" behind their backs.
    monkeypatch.setattr("apex._rust_bridge.RUST_AVAILABLE", False)
    return home


@pytest.fixture
def write_model_marker(tmp_apex_home: Path) -> Callable[[str, str], Path]:
    """Write a portable model-state marker and return its path."""

    def write(model_id: str, state: str) -> Path:
        key = hashlib.sha256(model_id.encode("utf-8")).hexdigest()
        marker_dir = tmp_apex_home / ".state" / "models" / "v1"
        marker_dir.mkdir(exist_ok=True)
        marker = marker_dir / f"{key}.{state}"
        marker.write_text(model_id + "\n", encoding="utf-8")
        return marker

    return write

