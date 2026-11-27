"""Tests for the 5 use-case benchmark datasets and scorers.

Tests verify:
1. Each dataset can be instantiated with correct attributes
2. Each dataset loads synthetic records (no HuggingFace download)
3. Records have expected fields
4. Each scorer can be instantiated
5. Coding task scorer can score a correct answer
6. Email triage scorer handles exact match
7. CLI factory functions work for all 5 benchmarks
"""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: I001

import pytest

# ---------------------------------------------------------------------------
# Dataset instantiation and loading
# ---------------------------------------------------------------------------


class TestEmailTriageDataset:
    def test_instantiation(self) -> None:
        from apex.evals.datasets.email_triage import EmailTriageDataset

        ds = EmailTriageDataset()
        assert ds.dataset_id == "email_triage"
        assert ds.dataset_name == "Email Triage"

    def test_load(self) -> None:
        from apex.evals.datasets.email_triage import EmailTriageDataset

        ds = EmailTriageDataset()
        ds.load(max_samples=5, seed=42)
        assert ds.size() == 5
        records = list(ds.iter_records())
        assert len(records) == 5
        r = records[0]
        assert r.record_id.startswith("email-triage-")
        assert r.category == "use-case"
        assert "urgency" in r.metadata
        assert "category" in r.metadata

    def test_load_all(self) -> None:
        from apex.evals.datasets.email_triage import EmailTriageDataset

        ds = EmailTriageDataset()
        ds.load()
        assert ds.size() == 30


class TestMorningBriefDataset:
    def test_instantiation(self) -> None:
        from apex.evals.datasets.morning_brief import MorningBriefDataset

        ds = MorningBriefDataset()
        assert ds.dataset_id == "morning_brief"
        assert ds.dataset_name == "Morning Brief"

    def test_load(self) -> None:
        from apex.evals.datasets.morning_brief import MorningBriefDataset

        ds = MorningBriefDataset()
        ds.load(max_samples=5, seed=42)
        assert ds.size() == 5
        records = list(ds.iter_records())
        r = records[0]
        assert r.record_id.startswith("morning-brief-")
        assert r.reference  # key_priorities not empty

    def test_load_all(self) -> None:
        from apex.evals.datasets.morning_brief import MorningBriefDataset

        ds = MorningBriefDataset()
        ds.load()
        assert ds.size() == 15


class TestResearchMiningDataset:
    def test_instantiation(self) -> None:
        from apex.evals.datasets.research_mining import ResearchMiningDataset

        ds = ResearchMiningDataset()
        assert ds.dataset_id == "research_mining"
        assert ds.dataset_name == "Research Mining"

    def test_load(self) -> None:
        from apex.evals.datasets.research_mining import ResearchMiningDataset

        ds = ResearchMiningDataset()
        ds.load(max_samples=5, seed=42)
        assert ds.size() == 5
        records = list(ds.iter_records())
        r = records[0]
        assert r.record_id.startswith("research-mining-")
        assert "domain" in r.metadata

    def test_load_all(self) -> None:
        from apex.evals.datasets.research_mining import ResearchMiningDataset

        ds = ResearchMiningDataset()
        ds.load()
        assert ds.size() == 31


class TestKnowledgeBaseDataset:
    def test_instantiation(self) -> None:
        from apex.evals.datasets.knowledge_base import KnowledgeBaseDataset

        ds = KnowledgeBaseDataset()
        assert ds.dataset_id == "knowledge_base"
        assert ds.dataset_name == "Knowledge Base"

    def test_load(self) -> None:
        from apex.evals.datasets.knowledge_base import KnowledgeBaseDataset

        ds = KnowledgeBaseDataset()
        ds.load(max_samples=5, seed=42)
        assert ds.size() == 5
        records = list(ds.iter_records())
        r = records[0]
        assert r.record_id.startswith("knowledge-base-")
        assert r.reference  # answer not empty

    def test_load_all(self) -> None:
        from apex.evals.datasets.knowledge_base import KnowledgeBaseDataset

        ds = KnowledgeBaseDataset()
        ds.load()
        assert ds.size() == 30


class TestCodingTaskDataset:
    def test_instantiation(self) -> None:
        from apex.evals.datasets.coding_task import CodingTaskDataset

        ds = CodingTaskDataset()
        assert ds.dataset_id == "coding_task"
        assert ds.dataset_name == "Coding Task"

    def test_load(self) -> None:
        from apex.evals.datasets.coding_task import CodingTaskDataset

        ds = CodingTaskDataset()
        ds.load(max_samples=5, seed=42)
        assert ds.size() == 5
        records = list(ds.iter_records())
        r = records[0]
        assert r.record_id.startswith("coding-task-")
        assert "test_cases" in r.metadata
        assert "signature" in r.metadata

    def test_load_all(self) -> None:
        from apex.evals.datasets.coding_task import CodingTaskDataset

        ds = CodingTaskDataset()
        ds.load()
        assert ds.size() == 29


# ---------------------------------------------------------------------------
# Scorer instantiation
# ---------------------------------------------------------------------------


class TestScorerInstantiation:
    def _mock_backend(self):
        return MagicMock()

    def test_email_triage_scorer(self) -> None:
        from apex.evals.scorers.email_triage import EmailTriageScorer

        scorer = EmailTriageScorer(self._mock_backend(), "gpt-5-mini")
        assert scorer.scorer_id == "email_triage"

    def test_morning_brief_scorer(self) -> None:
        from apex.evals.scorers.morning_brief import MorningBriefScorer

        scorer = MorningBriefScorer(self._mock_backend(), "gpt-5-mini")
        assert scorer.scorer_id == "morning_brief"

    def test_research_mining_scorer(self) -> None:
        from apex.evals.scorers.research_mining import ResearchMiningScorer

        scorer = ResearchMiningScorer(self._mock_backend(), "gpt-5-mini")
        assert scorer.scorer_id == "research_mining"

    def test_knowledge_base_scorer(self) -> None:
        from apex.evals.scorers.knowledge_base import KnowledgeBaseScorer

        scorer = KnowledgeBaseScorer(self._mock_backend(), "gpt-5-mini")
        assert scorer.scorer_id == "knowledge_base"

    def test_coding_task_scorer(self) -> None:
        from apex.evals.scorers.coding_task import CodingTaskScorer

        scorer = CodingTaskScorer(self._mock_backend(), "gpt-5-mini")
        assert scorer.scorer_id == "coding_task"


# ---------------------------------------------------------------------------
# Scorer functional tests
# ---------------------------------------------------------------------------


class TestCodingTaskScoring:
    """Test the coding task scorer with actual code execution."""

    def test_correct_answer(self) -> None:
        from apex.evals.core.types import EvalRecord
        from apex.evals.scorers.coding_task import CodingTaskScorer

        scorer = CodingTaskScorer()
        record = EvalRecord(
            record_id="test-1",
            problem="Write is_palindrome",
            reference="",
            category="use-case",
            subject="coding_task",
            metadata={
                "test_cases": (
                    'assert is_palindrome("racecar") == True\n'
                    'assert is_palindrome("hello") == False\n'
                    'assert is_palindrome("") == True'
                ),
            },
        )
        answer = "def is_palindrome(s):\n    return s == s[::-1]"
        is_correct, meta = scorer.score(record, answer)
        assert is_correct is True
        assert meta["tests_passed"] == 3
        assert meta["pass_rate"] == 1.0

    def test_incorrect_answer(self) -> None:
        from apex.evals.core.types import EvalRecord
        from apex.evals.scorers.coding_task import CodingTaskScorer

        scorer = CodingTaskScorer()
        record = EvalRecord(
            record_id="test-2",
            problem="Write add",
            reference="",
            category="use-case",
            metadata={
                "test_cases": ("assert add(1, 2) == 3\nassert add(0, 0) == 0"),
            },
        )
        # Wrong implementation
        answer = "def add(a, b):\n    return a * b"
        is_correct, meta = scorer.score(record, answer)
        assert is_correct is False

    def test_empty_answer(self) -> None:
        from apex.evals.core.types import EvalRecord
        from apex.evals.scorers.coding_task import CodingTaskScorer

        scorer = CodingTaskScorer()
        record = EvalRecord(
            record_id="test-3",
            problem="Write something",
            reference="",
            category="use-case",
            metadata={"test_cases": "assert True"},
        )
        is_correct, meta = scorer.score(record, "")
        assert is_correct is False
        assert meta["reason"] == "empty_response"


class TestEmailTriageScoring:
    """Test exact-match path of email triage scorer."""

    def test_exact_match(self) -> None:
        from apex.evals.core.types import EvalRecord
        from apex.evals.scorers.email_triage import EmailTriageScorer

        scorer = EmailTriageScorer(MagicMock(), "gpt-5-mini")
        record = EvalRecord(
            record_id="test-1",
            problem="...",
            reference="urgency: high\ncategory: action",
            category="use-case",
            metadata={"urgency": "high", "category": "action"},
        )
        answer = "urgency: high\ncategory: action\ndraft: I'll look into this."
        is_correct, meta = scorer.score(record, answer)
        assert is_correct is True
        assert meta["match_type"] == "exact"


# ---------------------------------------------------------------------------
# CLI factory tests
# ---------------------------------------------------------------------------


class TestCLIFactories:
    """Test that _build_dataset and _build_scorer work for new benchmarks."""

    @pytest.mark.parametrize(
        "benchmark",
        [
            "email_triage",
            "morning_brief",
            "research_mining",
            "knowledge_base",
            "coding_task",
        ],
    )
    def test_build_dataset(self, benchmark: str) -> None:
        from apex.evals.cli import _build_dataset

        ds = _build_dataset(benchmark)
        assert ds.dataset_id == benchmark

    @pytest.mark.parametrize(
        "benchmark",
        [
            "email_triage",
            "morning_brief",
            "research_mining",
            "knowledge_base",
            "coding_task",
        ],
    )
    def test_build_scorer(self, benchmark: str) -> None:
        from apex.evals.cli import _build_scorer

        scorer = _build_scorer(benchmark, MagicMock(), "gpt-5-mini")
        assert scorer.scorer_id == benchmark
