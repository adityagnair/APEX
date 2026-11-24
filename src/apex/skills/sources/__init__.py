"""Skill source resolvers — Hermes, OpenClaw, generic GitHub."""

from apex.skills.sources.base import ResolvedSkill, SourceResolver
from apex.skills.sources.github import GitHubResolver
from apex.skills.sources.hermes import HERMES_REPO_URL, HermesResolver
from apex.skills.sources.openclaw import OPENCLAW_REPO_URL, OpenClawResolver

__all__ = [
    "GitHubResolver",
    "HERMES_REPO_URL",
    "HermesResolver",
    "OPENCLAW_REPO_URL",
    "OpenClawResolver",
    "ResolvedSkill",
    "SourceResolver",
]

