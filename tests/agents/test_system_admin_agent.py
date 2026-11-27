"""Tests for the system_admin agent."""

from __future__ import annotations

from apex.agents.system_admin import SystemAdminAgent
from apex.core.registry import AgentRegistry


class _Engine:
    """Minimal engine double that answers without requesting tools."""

    engine_id = "fake"

    def __init__(self, content: str = "Two printers are installed.") -> None:
        self.content = content
        self.calls = 0

    def generate(self, messages, **kwargs):
        self.calls += 1
        return {"content": self.content, "tool_calls": [], "usage": {}}


def test_agent_is_registered():
    # The autouse fixture clears registries between tests, so re-register the
    # class the same way the module decorator does at import time.
    AgentRegistry.register("system_admin")(SystemAdminAgent)

    assert AgentRegistry.contains("system_admin")
    assert AgentRegistry.get("system_admin") is SystemAdminAgent


def test_agent_grants_its_own_tools():
    agent = SystemAdminAgent(_Engine(), "fake-model")

    names = {tool.spec.name for tool in agent._tools}

    assert {"file_manager", "system_devices"} <= names


def test_run_returns_the_model_answer():
    engine = _Engine()
    agent = SystemAdminAgent(engine, "fake-model", max_turns=2)

    result = agent.run("what printers are connected?")

    assert result.content == "Two printers are installed."
    assert result.turns == 1
    assert engine.calls == 1


def test_system_prompt_describes_the_tools():
    agent = SystemAdminAgent(_Engine(), "fake-model")

    prompt = agent._system_prompt_text()

    assert "System Manager" in prompt
    assert "file_manager" in prompt
    assert "system_devices" in prompt


def test_explicit_prompt_overrides_the_default():
    agent = SystemAdminAgent(
        _Engine(), "fake-model", system_prompt="Custom manager prompt"
    )

    assert agent._system_prompt_text() == "Custom manager prompt"
