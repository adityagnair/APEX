"""File manager tool — browse, locate and organise files on the host machine.

This is the filesystem counterpart of the shell: an agent can list a folder,
find files by name/size/date, inspect them, and copy, move, rename or delete
them without composing platform-specific shell commands.  Every path is
checked against ``security.allowed_dirs`` and the sensitive-file policy before
anything is read or changed.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import string
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, List, Optional

from apex.core.registry import ToolRegistry
from apex.core.types import ToolResult
from apex.tools._paths import resolve_allowed_dirs
from apex.tools._stubs import BaseTool, ToolSpec

# Listing / search caps keep tool output inside a model's context window.
_MAX_LIST_ENTRIES = 200
_MAX_FIND_RESULTS = 100
_MAX_WALK_ENTRIES = 100_000
_MAX_DEPTH_LIMIT = 12

# Directories that are never worth walking by default: they are huge and
# their contents are dependencies, not user documents.
_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "site-packages",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)

_ACTIONS = (
    "roots",
    "list",
    "find",
    "info",
    "du",
    "mkdir",
    "copy",
    "move",
    "delete",
    "open",
)


def _human_size(size: float) -> str:
    """Format a byte count for humans (and for a model reading the output)."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _stamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _split_patterns(raw: str) -> List[str]:
    return [part.strip() for part in raw.replace(",", " ").split() if part.strip()]


def _matches(name: str, pattern: str) -> bool:
    """Match a file name against a glob, falling back to substring matching."""
    lowered = name.lower()
    needle = pattern.lower()
    if any(char in needle for char in "*?["):
        return fnmatch.fnmatch(lowered, needle)
    return needle in lowered


@ToolRegistry.register("file_manager")
class FileManagerTool(BaseTool):
    """Browse, search and organise files without shell commands."""

    tool_id = "file_manager"

    def __init__(self, allowed_dirs: Optional[List[str]] = None) -> None:
        self._allowed_dirs = [
            Path(d).expanduser().resolve() for d in resolve_allowed_dirs(allowed_dirs)
        ]

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_manager",
            description=(
                "Manage files on this computer. Actions: 'roots' shows where you "
                "may look (home, drives, allowed folders); 'list' lists a "
                "directory; 'find' locates files by name (substring or glob) "
                "with optional size/date filters; 'info' describes one path; "
                "'du' reports folder sizes; 'mkdir', 'copy', 'move', 'delete' "
                "change the filesystem ('delete' is permanent and needs "
                "confirm=true); 'open' launches a file or folder in the default "
                "application."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(_ACTIONS),
                        "description": "Operation to perform.",
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "Target directory or file. Defaults to the home "
                            "directory ('roots' ignores it)."
                        ),
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination path for 'copy' and 'move'.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": (
                            "For 'find': file name text or glob, e.g. 'invoice' "
                            "or '*.pdf'. Several patterns may be space separated."
                        ),
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "For 'find': how deep to recurse (default 4).",
                    },
                    "min_bytes": {
                        "type": "integer",
                        "description": "For 'find': only entries at least this large.",
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "For 'find': only entries at most this large.",
                    },
                    "modified_within_days": {
                        "type": "number",
                        "description": (
                            "For 'find': only entries modified in the last N days."
                        ),
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["files", "dirs", "any"],
                        "description": "For 'find': what to return (default files).",
                    },
                    "hidden": {
                        "type": "boolean",
                        "description": (
                            "Include dotfiles and dependency/cache directories. "
                            "Default false."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum entries to return (default 50).",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": (
                            "For 'copy'/'move': replace the destination if it "
                            "already exists. Default false."
                        ),
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "For 'delete': allow removing a directory tree.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": (
                            "For 'delete': must be true. Deletion is permanent."
                        ),
                    },
                },
                "required": ["action"],
            },
            category="filesystem",
            required_capabilities=["file:read", "file:write"],
        )

    # ------------------------------------------------------------------
    # Path policy helpers
    # ------------------------------------------------------------------

    def _is_path_allowed(self, path: Path) -> bool:
        if not self._allowed_dirs:
            return True
        resolved = path.resolve()
        return any(
            resolved == directory or resolved.is_relative_to(directory)
            for directory in self._allowed_dirs
        )

    def _resolve(self, raw: Optional[str], *, default: Optional[Path] = None) -> Path:
        if not raw:
            if default is not None:
                return default
            if self._allowed_dirs:
                return self._allowed_dirs[0]
            return Path.home()
        path = Path(os.path.expandvars(os.path.expanduser(raw)))
        if not path.is_absolute() and self._allowed_dirs:
            path = self._allowed_dirs[0] / path
        return path

    def _deny(self, action: str, path: Path, reason: str) -> ToolResult:
        return ToolResult(
            tool_name="file_manager",
            content=f"Access denied for {action}: {path} — {reason}",
            success=False,
            metadata={"action": action, "path": str(path)},
        )

    def _guard(self, action: str, path: Path, *, write: bool) -> Optional[ToolResult]:
        """Return a denial result when *path* may not be touched, else None."""
        if not self._is_path_allowed(path):
            return self._deny(action, path, "outside the allowed directories")
        from apex.security.file_policy import is_sensitive_file

        if is_sensitive_file(path):
            return self._deny(action, path, "it is a sensitive file (secrets/keys)")
        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def execute(self, **params: Any) -> ToolResult:
        action = str(params.get("action", "") or "").strip().lower()
        if action not in _ACTIONS:
            return ToolResult(
                tool_name="file_manager",
                content=(
                    f"Unknown action {action!r}. "
                    f"Valid actions: {', '.join(_ACTIONS)}."
                ),
                success=False,
            )
        handler = getattr(self, f"_action_{action}")
        try:
            return handler(params)
        except OSError as exc:
            return ToolResult(
                tool_name="file_manager",
                content=f"{action} failed: {exc}",
                success=False,
                metadata={"action": action},
            )

    def _action_roots(self, params: dict[str, Any]) -> ToolResult:
        roots: List[Path] = [Path.home()]
        roots.extend(self._allowed_dirs)
        drives: List[Path] = []
        if os.name == "nt":
            for letter in string.ascii_uppercase:
                candidate = Path(f"{letter}:\\")
                try:
                    if candidate.exists():
                        drives.append(candidate)
                except OSError:
                    continue
        lines = ["Searchable locations:"]
        seen: set[str] = set()
        for root in roots:
            resolved = str(root.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            lines.append(f"  {resolved}")
        if drives:
            lines.append("Drives:")
            for drive in drives:
                resolved = str(drive.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                lines.append(f"  {resolved}")
        if self._allowed_dirs:
            lines.append(
                "Policy: only paths inside the folders listed above may be touched."
            )
        else:
            lines.append("Policy: no directory restriction is configured.")
        return ToolResult(
            tool_name="file_manager",
            content="\n".join(lines),
            success=True,
            metadata={"action": "roots", "roots": sorted(seen)},
        )

    def _action_list(self, params: dict[str, Any]) -> ToolResult:
        path = self._resolve(params.get("path"))
        if not path.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Not found: {path}",
                success=False,
                metadata={"action": "list", "path": str(path)},
            )
        if not path.is_dir():
            return ToolResult(
                tool_name="file_manager",
                content=f"Not a directory: {path}. Use action='info' for a file.",
                success=False,
                metadata={"action": "list", "path": str(path)},
            )
        denial = self._guard("list", path, write=False)
        if denial is not None:
            return denial

        show_hidden = bool(params.get("hidden", False))
        limit = self._limit(params, _MAX_LIST_ENTRIES)
        try:
            entries = sorted(
                path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())
            )
        except PermissionError as exc:
            return ToolResult(
                tool_name="file_manager",
                content=f"Permission denied listing {path}: {exc}",
                success=False,
                metadata={"action": "list", "path": str(path)},
            )

        rows: List[str] = []
        dirs = files = 0
        skipped = 0
        for entry in entries:
            name = entry.name
            if not show_hidden and name.startswith("."):
                skipped += 1
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue
            if entry.is_dir():
                dirs += 1
                rows.append(f"  [DIR ]  {name}/")
            else:
                files += 1
                restricted = ""
                try:
                    from apex.security.file_policy import is_sensitive_file

                    if is_sensitive_file(entry):
                        restricted = "  (restricted)"
                except Exception:
                    restricted = ""
                rows.append(
                    f"  [FILE]  {name:<40} {_human_size(stat.st_size):>9}"
                    f"  {_stamp(stat.st_mtime)}{restricted}"
                )
            if len(rows) >= limit:
                rows.append(f"  ... more entries not shown (limit {limit})")
                break

        header = (
            f"Directory: {path.resolve()} "
            f"({dirs} dirs, {files} files, {skipped} hidden skipped)"
        )
        body = "\n".join(rows) if rows else "  (empty)"
        return ToolResult(
            tool_name="file_manager",
            content=f"{header}\n{body}",
            success=True,
            metadata={
                "action": "list",
                "path": str(path.resolve()),
                "dirs": dirs,
                "files": files,
            },
        )

    def _action_find(self, params: dict[str, Any]) -> ToolResult:
        raw_pattern = str(params.get("pattern", "") or "").strip()
        if not raw_pattern:
            return ToolResult(
                tool_name="file_manager",
                content="'find' needs a pattern, e.g. '*.pdf' or 'invoice'.",
                success=False,
                metadata={"action": "find"},
            )
        root = self._resolve(params.get("path"))
        if not root.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Search root not found: {root}",
                success=False,
                metadata={"action": "find", "path": str(root)},
            )
        if not root.is_dir():
            return ToolResult(
                tool_name="file_manager",
                content=f"Search root is not a directory: {root}",
                success=False,
                metadata={"action": "find", "path": str(root)},
            )
        denial = self._guard("find", root, write=False)
        if denial is not None:
            return denial

        patterns = _split_patterns(raw_pattern)
        kind = str(params.get("kind", "files") or "files").lower()
        if kind not in {"files", "dirs", "any"}:
            kind = "files"
        show_hidden = bool(params.get("hidden", False))
        depth = self._limit(params, _MAX_DEPTH_LIMIT, key="max_depth", fallback=4)
        limit = self._limit(params, _MAX_FIND_RESULTS, key="limit", fallback=50)
        min_bytes = self._optional_int(params.get("min_bytes"))
        max_bytes = self._optional_int(params.get("max_bytes"))
        since: Optional[float] = None
        days = params.get("modified_within_days")
        if days is not None:
            try:
                since = (datetime.now() - timedelta(days=float(days))).timestamp()
            except (TypeError, ValueError):
                since = None

        matches: List[str] = []
        scanned = 0
        truncated = False
        for candidate, is_dir in self._walk(root, depth, show_hidden):
            scanned += 1
            if scanned > _MAX_WALK_ENTRIES:
                truncated = True
                break
            name = candidate.name
            if not any(_matches(name, pattern) for pattern in patterns):
                continue
            if is_dir and kind == "files":
                continue
            if not is_dir and kind == "dirs":
                continue
            try:
                stat = candidate.stat()
            except OSError:
                continue
            if min_bytes is not None and stat.st_size < min_bytes:
                continue
            if max_bytes is not None and stat.st_size > max_bytes:
                continue
            if since is not None and stat.st_mtime < since:
                continue
            suffix = "/" if is_dir else ""
            size = "<dir>" if is_dir else _human_size(stat.st_size)
            matches.append(
                f"  {_stamp(stat.st_mtime)}  {size:>9}  {candidate}{suffix}"
            )
            if len(matches) >= limit:
                truncated = True
                break

        scanned_total = min(scanned, _MAX_WALK_ENTRIES)
        header = (
            f"Found {len(matches)} match(es) for {', '.join(patterns)} "
            f"under {root.resolve()} (scanned {scanned_total} entries)"
        )
        body = "\n".join(matches) if matches else "  (no matches)"
        note = "\n  ... results truncated by the search limit" if truncated else ""
        return ToolResult(
            tool_name="file_manager",
            content=f"{header}\n{body}{note}",
            success=True,
            metadata={
                "action": "find",
                "path": str(root.resolve()),
                "count": len(matches),
                "truncated": truncated,
            },
        )

    def _action_info(self, params: dict[str, Any]) -> ToolResult:
        path = self._resolve(params.get("path"))
        if not path.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Not found: {path}",
                success=False,
                metadata={"action": "info", "path": str(path)},
            )
        denial = self._guard("info", path, write=False)
        if denial is not None:
            return denial
        stat = path.stat()
        lines = [
            f"Path:      {path.resolve()}",
            f"Type:      {'directory' if path.is_dir() else 'file'}",
            f"Size:      {_human_size(stat.st_size)} ({stat.st_size} bytes)",
            f"Created:   {_stamp(stat.st_ctime)}",
            f"Modified:  {_stamp(stat.st_mtime)}",
            f"Accessed:  {_stamp(stat.st_atime)}",
            f"Mode:      {oct(stat.st_mode & 0o777)}",
        ]
        if path.suffix:
            lines.append(f"Extension: {path.suffix}")
        if path.is_dir():
            children = 0
            subdirs = 0
            try:
                for child in path.iterdir():
                    children += 1
                    if child.is_dir():
                        subdirs += 1
            except OSError:
                pass
            lines.append(f"Contains:  {children} entries ({subdirs} dirs)")
        return ToolResult(
            tool_name="file_manager",
            content="\n".join(lines),
            success=True,
            metadata={
                "action": "info",
                "path": str(path.resolve()),
                "size_bytes": stat.st_size,
                "is_dir": path.is_dir(),
            },
        )

    def _action_du(self, params: dict[str, Any]) -> ToolResult:
        path = self._resolve(params.get("path"))
        if not path.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Not found: {path}",
                success=False,
                metadata={"action": "du", "path": str(path)},
            )
        denial = self._guard("du", path, write=False)
        if denial is not None:
            return denial
        if path.is_file():
            size = path.stat().st_size
            return ToolResult(
                tool_name="file_manager",
                content=f"{path.resolve()}: {_human_size(size)} ({size} bytes)",
                success=True,
                metadata={"action": "du", "path": str(path), "size_bytes": size},
            )

        total = 0
        files = 0
        children: List[tuple[str, int]] = []
        show_hidden = bool(params.get("hidden", False))
        for child in sorted(
            path.iterdir(), key=lambda item: item.name.lower()
        ):
            if not show_hidden and child.name.startswith("."):
                continue
            child_total, child_files = self._dir_size(child, show_hidden)
            total += child_total
            files += child_files
            children.append((child.name, child_total))
        children.sort(key=lambda item: item[1], reverse=True)
        lines = [
            f"Folder: {path.resolve()}",
            f"Total:  {_human_size(total)} across {files} files",
            "",
            "Largest entries:",
        ]
        for name, size in children[:10]:
            lines.append(f"  {_human_size(size):>9}  {name}")
        return ToolResult(
            tool_name="file_manager",
            content="\n".join(lines),
            success=True,
            metadata={
                "action": "du",
                "path": str(path.resolve()),
                "size_bytes": total,
                "files": files,
            },
        )

    def _action_mkdir(self, params: dict[str, Any]) -> ToolResult:
        path = self._resolve(params.get("path"))
        denial = self._guard("mkdir", path, write=True)
        if denial is not None:
            return denial
        if path.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Already exists: {path}",
                success=True,
                metadata={"action": "mkdir", "path": str(path), "created": False},
            )
        path.mkdir(parents=True, exist_ok=bool(params.get("parents", True)))
        return ToolResult(
            tool_name="file_manager",
            content=f"Created directory: {path.resolve()}",
            success=True,
            metadata={"action": "mkdir", "path": str(path), "created": True},
        )

    def _action_copy(self, params: dict[str, Any]) -> ToolResult:
        return self._transfer("copy", params)

    def _action_move(self, params: dict[str, Any]) -> ToolResult:
        return self._transfer("move", params)

    def _transfer(self, action: str, params: dict[str, Any]) -> ToolResult:
        source = self._resolve(params.get("path"))
        if not params.get("destination"):
            return ToolResult(
                tool_name="file_manager",
                content=f"'{action}' needs a destination path.",
                success=False,
                metadata={"action": action},
            )
        destination = self._resolve(params.get("destination"))
        overwrite = bool(params.get("overwrite", False))
        if not source.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Source not found: {source}",
                success=False,
                metadata={"action": action, "path": str(source)},
            )
        from apex.security.file_policy import is_sensitive_file

        for label, path in (("source", source), ("destination", destination)):
            if not self._is_path_allowed(path):
                return self._deny(
                    action, path, f"{label} is outside the allowed directories"
                )
            if is_sensitive_file(path):
                return self._deny(action, path, f"{label} is a sensitive file")
        # Copying a directory into itself would recurse forever.
        if source.is_dir() and destination.resolve().is_relative_to(source.resolve()):
            return ToolResult(
                tool_name="file_manager",
                content=f"Cannot {action} {source} into itself ({destination}).",
                success=False,
                metadata={"action": action},
            )
        existed = destination.exists()
        if destination.is_dir():
            destination = destination / source.name
            existed = destination.exists()
        if existed and not overwrite:
            return ToolResult(
                tool_name="file_manager",
                content=(
                    f"{destination} already exists. Pass overwrite=true to replace it."
                ),
                success=False,
                metadata={"action": action, "path": str(destination)},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if action == "copy":
            if source.is_dir():
                if existed:
                    shutil.rmtree(destination)
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        else:
            if existed:
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            shutil.move(str(source), str(destination))
        verb = "Copied" if action == "copy" else "Moved"
        return ToolResult(
            tool_name="file_manager",
            content=f"{verb} {source} -> {destination}",
            success=True,
            metadata={
                "action": action,
                "source": str(source.resolve()),
                "destination": str(destination.resolve()),
            },
        )

    def _action_delete(self, params: dict[str, Any]) -> ToolResult:
        path = self._resolve(params.get("path"))
        confirm = params.get("confirm")
        if confirm is not True and str(confirm).strip().lower() not in {
            "true",
            "yes",
            "confirm",
        }:
            return ToolResult(
                tool_name="file_manager",
                content=(
                    "Refusing to delete without confirmation. Repeat the call with "
                    "confirm=true once you are sure — deletion is permanent."
                ),
                success=False,
                metadata={"action": "delete", "path": str(path)},
            )
        if not path.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Not found: {path}",
                success=False,
                metadata={"action": "delete", "path": str(path)},
            )
        denial = self._guard("delete", path, write=True)
        if denial is not None:
            return denial
        resolved = path.resolve()
        protected = {Path.home().resolve(), *self._allowed_dirs}
        if resolved in protected:
            return ToolResult(
                tool_name="file_manager",
                content=f"Refusing to delete a protected root: {resolved}",
                success=False,
                metadata={"action": "delete", "path": str(resolved)},
            )
        if path.is_dir():
            if not params.get("recursive"):
                return ToolResult(
                    tool_name="file_manager",
                    content=(
                        f"{resolved} is a directory. Pass recursive=true to remove "
                        "it and everything inside it."
                    ),
                    success=False,
                    metadata={"action": "delete", "path": str(resolved)},
                )
            shutil.rmtree(path)
        else:
            path.unlink()
        return ToolResult(
            tool_name="file_manager",
            content=f"Deleted {resolved}",
            success=True,
            metadata={"action": "delete", "path": str(resolved)},
        )

    def _action_open(self, params: dict[str, Any]) -> ToolResult:
        path = self._resolve(params.get("path"))
        if not path.exists():
            return ToolResult(
                tool_name="file_manager",
                content=f"Not found: {path}",
                success=False,
                metadata={"action": "open", "path": str(path)},
            )
        denial = self._guard("open", path, write=False)
        if denial is not None:
            return denial
        target = str(path.resolve())
        command: List[str]
        if os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
            return ToolResult(
                tool_name="file_manager",
                content=f"Opened {target} with its default application.",
                success=True,
                metadata={"action": "open", "path": target},
            )
        if sys.platform == "darwin":
            command = ["open", target]
        else:
            command = ["xdg-open", target]
        subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return ToolResult(
            tool_name="file_manager",
            content=f"Opened {target} with its default application.",
            success=True,
            metadata={"action": "open", "path": target},
        )

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _limit(
        params: dict[str, Any],
        cap: int,
        *,
        key: str = "limit",
        fallback: Optional[int] = None,
    ) -> int:
        raw = params.get(key, fallback)
        try:
            value = int(raw) if raw is not None else cap
        except (TypeError, ValueError):
            value = cap
        return max(1, min(value, cap))

    @staticmethod
    def _optional_int(raw: Any) -> Optional[int]:
        if raw is None or raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _walk(
        self, root: Path, depth: int, show_hidden: bool
    ) -> Iterator[tuple[Path, bool]]:
        """Yield ``(path, is_dir)`` below *root* down to *depth* levels."""
        stack: List[tuple[Path, int]] = [(root, 0)]
        while stack:
            current, level = stack.pop()
            try:
                children = sorted(current.iterdir(), key=lambda item: item.name.lower())
            except OSError:
                continue
            for child in children:
                try:
                    is_dir = child.is_dir()
                except OSError:
                    continue
                if not show_hidden and (
                    child.name.startswith(".") or child.name.lower() in _SKIP_DIR_NAMES
                ):
                    continue
                yield child, is_dir
                if is_dir and level + 1 < depth:
                    stack.append((child, level + 1))

    def _dir_size(self, path: Path, show_hidden: bool) -> tuple[int, int]:
        if path.is_file():
            try:
                return path.stat().st_size, 1
            except OSError:
                return 0, 0
        total = 0
        files = 0
        for candidate, is_dir in self._walk(path, _MAX_DEPTH_LIMIT, show_hidden):
            if is_dir:
                continue
            try:
                total += candidate.stat().st_size
            except OSError:
                continue
            files += 1
        return total, files


__all__ = ["FileManagerTool"]
