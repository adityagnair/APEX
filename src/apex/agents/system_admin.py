"""SystemAdminAgent — an agent that manages the computer it runs on.

Where the coding agents work inside a repository, this one works on the
machine: it browses and searches the filesystem, reports the hardware attached
to the host (printers, Bluetooth, USB, audio, network, disks, displays,
battery), and performs the file operations a user asks for — copy, move,
rename, delete, open.

It is a thin orchestration layer over two tools (``file_manager`` and
``system_devices``) plus ``file_read``/``think``, and it follows the same
OpenAI function-calling loop as :class:`~apex.agents.orchestrator.OrchestratorAgent`.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from apex.agents._stubs import AgentContext, AgentResult, ToolUsingAgent
from apex.core.events import EventBus
from apex.core.registry import AgentRegistry
from apex.core.types import Message, Role, ToolCall, ToolResult
from apex.engine._stubs import InferenceEngine
from apex.tools._stubs import BaseTool

logger = logging.getLogger(__name__)

#: Tools this agent grants itself when the caller supplies none.
DEFAULT_TOOL_NAMES = ("file_manager", "system_devices", "file_read", "think")

SYSTEM_PROMPT = """You are the System Manager, an assistant that operates the \
computer you are running on rather than a code repository.

You can:
- Find and organise files: list folders, locate files by name, size or date, \
inspect them, create folders, copy, move, rename, delete, and open things in \
their default application (`file_manager`).
- Report the host and its hardware: operating system, CPU, memory, disk space, \
printers and print jobs, Bluetooth and USB devices, audio devices, network \
adapters, displays and battery (`system_devices`).
- Read a text file's contents (`file_read`) and reason step by step (`think`).

How to work:
1. Inspect before you act. Call `roots` or `system_devices`/`file_manager` \
first so your answer is based on what is actually on this machine.
2. Report only what the tools returned. If a query returns nothing, say that \
plainly instead of guessing device names, paths or sizes.
3. Deleting is permanent. Ask for explicit confirmation in your reply and \
only call `delete` with confirm=true when the user has clearly asked for that \
deletion. Prefer copying to a backup folder when the user seems unsure.
4. Never read, copy or delete credential material (SSH keys, `.env` files, \
browser profiles, password stores). If a tool denies access, accept it and \
explain the restriction.
5. Stay inside the directory policy. If a path is outside the allowed folders, \
tell the user which folder they would need to allow instead of retrying.
6. Prefer several small, verifiable tool calls over one large risky one, and \
mention the exact paths you touched.

Answer in short, structured sentences. When the user asks what is connected, \
group the findings by device type and include the key fields (printer status, \
Bluetooth/USB class, disk free space)."""


@AgentRegistry.register("system_admin")
class SystemAdminAgent(ToolUsingAgent):
    """Filesystem and device manager for the host machine."""

    agent_id = "system_admin"
    _default_temperature = 0.2
    _default_max_tokens = 1024
    _default_max_turns = 12

    def __init__(
        self,
        engine: InferenceEngine,
        model: str,
        *,
        tools: Optional[List[BaseTool]] = None,
        bus: Optional[EventBus] = None,
        max_turns: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        prompt_builder: Optional[Any] = None,
        capability_policy: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        agent_id: Optional[str] = None,
        interactive: bool = False,
        confirm_callback: Optional[Any] = None,
    ) -> None:
        super().__init__(
            engine,
            model,
            tools=tools or self._default_tools(),
            bus=bus,
            max_turns=max_turns,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_builder=prompt_builder,
            capability_policy=capability_policy,
            rate_limiter=rate_limiter,
            agent_id=agent_id,
            interactive=interactive,
            confirm_callback=confirm_callback,
        )
        self._system_prompt = system_prompt

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_tools() -> List[BaseTool]:
        """Instantiate this agent's own toolkit from the registry."""
        from apex.agents.tool_resolver import ensure_registries_populated
        from apex.core.registry import ToolRegistry

        # Populates (or re-populates, after a registry clear) the built-ins so
        # this agent can be constructed before anything else imported them.
        try:
            ensure_registries_populated()
        except Exception:  # pragma: no cover - import guard
            logger.debug("Could not populate the tool registry", exc_info=True)

        instances: List[BaseTool] = []
        for name in DEFAULT_TOOL_NAMES:
            if not ToolRegistry.contains(name):
                logger.warning("System manager tool %r is not registered", name)
                continue
            registered = ToolRegistry.get(name)
            try:
                if isinstance(registered, BaseTool):
                    instances.append(registered)
                else:
                    instances.append(registered())
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Could not instantiate tool %r: %s", name, exc)
        return instances

    def _system_prompt_text(self) -> str:
        if self._system_prompt:
            return self._system_prompt
        from apex.tools._stubs import build_tool_descriptions

        if not self._tools:
            return SYSTEM_PROMPT
        catalog = build_tool_descriptions(self._tools, include_category=True)
        return f"{SYSTEM_PROMPT}\n\n## Available tools\n{catalog}"

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        self._emit_turn_start(input)

        messages = self._build_messages(
            input,
            context,
            system_prompt=self._system_prompt_text(),
        )
        openai_tools = self._executor.get_openai_tools() if self._tools else []

        tool_results: List[ToolResult] = []
        turns = 0
        content = ""

        for _turn in range(self._max_turns):
            turns += 1
            if self._loop_guard:
                messages = self._loop_guard.compress_context(messages)

            gen_kwargs: dict[str, Any] = {}
            if openai_tools:
                gen_kwargs["tools"] = openai_tools

            result = self._generate(messages, **gen_kwargs)
            content = result.get("content", "")
            raw_calls = result.get("tool_calls", []) or []

            if not raw_calls:
                content = self._check_continuation(result, messages)
                content = self._strip_think_tags(content)
                self._emit_turn_end(turns=turns, content_length=len(content))
                return AgentResult(
                    content=content,
                    tool_results=tool_results,
                    turns=turns,
                )

            calls = [
                ToolCall(
                    id=call.get("id", f"call_{index}"),
                    name=call.get("name", ""),
                    arguments=call.get("arguments", "{}"),
                )
                for index, call in enumerate(raw_calls)
            ]
            messages.append(
                Message(role=Role.ASSISTANT, content=content, tool_calls=calls)
            )

            for call in calls:
                verdict = (
                    self._loop_guard.check_call(call.name, call.arguments)
                    if self._loop_guard
                    else None
                )
                if verdict is not None and verdict.blocked:
                    tool_result = ToolResult(
                        tool_name=call.name,
                        content=f"Loop guard: {verdict.reason}",
                        success=False,
                    )
                else:
                    tool_result = self._executor.execute(call)
                tool_results.append(tool_result)
                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=tool_result.content,
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

        final = self._strip_think_tags(content) if content else ""
        return self._max_turns_result(
            tool_results,
            turns,
            content=final,
        )


__all__ = ["DEFAULT_TOOL_NAMES", "SYSTEM_PROMPT", "SystemAdminAgent"]
