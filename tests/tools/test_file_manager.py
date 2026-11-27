"""Tests for the file_manager tool."""

from __future__ import annotations

import pytest

from apex.tools.file_manager import FileManagerTool


@pytest.fixture()
def workspace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "invoice-2024.pdf").write_bytes(b"x" * 2048)
    (tmp_path / "docs" / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "invoice-scan.jpg").write_bytes(b"y" * 512)
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def tool(workspace):
    return FileManagerTool(allowed_dirs=[str(workspace)])


def test_roots_lists_allowed_directories(tool, workspace):
    result = tool.execute(action="roots")

    assert result.success
    assert str(workspace.resolve()) in result.content


def test_list_reports_files_and_directories(tool, workspace):
    result = tool.execute(action="list", path=str(workspace))

    assert result.success
    assert "docs" in result.content
    assert "notes.txt" in result.content or "docs/" in result.content
    assert result.metadata["dirs"] == 2
    assert result.metadata["files"] == 0


def test_list_hidden_false_skips_dotfiles(tool, workspace):
    hidden = tool.execute(action="list", path=str(workspace), hidden=True)
    visible = tool.execute(action="list", path=str(workspace))

    assert ".env" in hidden.content
    assert ".env" not in visible.content


def test_list_rejects_a_file(tool, workspace):
    result = tool.execute(action="list", path=str(workspace / "docs" / "notes.txt"))

    assert not result.success
    assert "Not a directory" in result.content


def test_find_matches_substring_across_subdirectories(tool, workspace):
    result = tool.execute(action="find", path=str(workspace), pattern="invoice")

    assert result.success
    assert "invoice-2024.pdf" in result.content
    assert "invoice-scan.jpg" in result.content
    assert result.metadata["count"] == 2


def test_find_supports_globs_and_size_filters(tool, workspace):
    result = tool.execute(
        action="find",
        path=str(workspace),
        pattern="*.jpg",
        min_bytes=1024,
    )

    assert result.success
    assert result.metadata["count"] == 0

    result = tool.execute(action="find", path=str(workspace), pattern="*.jpg")
    assert result.metadata["count"] == 1


def test_find_kind_dirs_returns_directories(tool, workspace):
    result = tool.execute(
        action="find", path=str(workspace), pattern="doc", kind="dirs"
    )

    assert result.success
    assert "docs" in result.content


def test_find_requires_a_pattern(tool, workspace):
    result = tool.execute(action="find", path=str(workspace))

    assert not result.success
    assert "needs a pattern" in result.content


def test_info_reports_size_and_type(tool, workspace):
    result = tool.execute(action="info", path=str(workspace / "docs" / "notes.txt"))

    assert result.success
    assert result.metadata["size_bytes"] == 5
    assert "file" in result.content


def test_delete_requires_confirmation(tool, workspace):
    target = workspace / "docs" / "notes.txt"
    result = tool.execute(action="delete", path=str(target))

    assert not result.success
    assert "confirm" in result.content.lower()
    assert target.exists()


def test_delete_removes_file_when_confirmed(tool, workspace):
    target = workspace / "docs" / "notes.txt"
    result = tool.execute(action="delete", path=str(target), confirm=True)

    assert result.success
    assert not target.exists()


def test_delete_refuses_directory_without_recursive(tool, workspace):
    result = tool.execute(action="delete", path=str(workspace / "docs"), confirm=True)

    assert not result.success
    assert "recursive" in result.content


def test_delete_refuses_protected_root(tool, workspace):
    result = tool.execute(action="delete", path=str(workspace), confirm=True)

    assert not result.success
    assert "protected" in result.content
    assert workspace.exists()


def test_delete_refuses_sensitive_files(tool, workspace):
    result = tool.execute(action="delete", path=str(workspace / ".env"), confirm=True)

    assert not result.success
    assert (workspace / ".env").exists()


def test_copy_and_move_between_directories(tool, workspace):
    source = workspace / "docs" / "notes.txt"
    copied = workspace / "photos" / "notes.txt"

    copy_result = tool.execute(
        action="copy", path=str(source), destination=str(workspace / "photos")
    )
    assert copy_result.success
    assert copied.exists()

    moved = workspace / "docs" / "moved.txt"
    move_result = tool.execute(
        action="move", path=str(copied), destination=str(moved)
    )
    assert move_result.success
    assert moved.exists()
    assert not copied.exists()


def test_copy_does_not_overwrite_without_permission(tool, workspace):
    source = workspace / "docs" / "notes.txt"
    existing = workspace / "photos" / "notes.txt"
    existing.write_text("keep me", encoding="utf-8")

    result = tool.execute(
        action="copy", path=str(source), destination=str(existing)
    )

    assert not result.success
    assert existing.read_text(encoding="utf-8") == "keep me"

    forced = tool.execute(
        action="copy",
        path=str(source),
        destination=str(existing),
        overwrite=True,
    )
    assert forced.success
    assert existing.read_text(encoding="utf-8") == "hello"


def test_paths_outside_the_allowlist_are_denied(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x", encoding="utf-8")

    tool = FileManagerTool(allowed_dirs=[str(allowed)])

    result = tool.execute(action="list", path=str(outside))

    assert not result.success
    assert "outside the allowed directories" in result.content


def test_du_reports_total_size(tool, workspace):
    result = tool.execute(action="du", path=str(workspace))

    assert result.success
    assert result.metadata["files"] >= 3
    assert result.metadata["size_bytes"] >= 2048


def test_unknown_action_is_reported(tool):
    result = tool.execute(action="explode")

    assert not result.success
    assert "Unknown action" in result.content
