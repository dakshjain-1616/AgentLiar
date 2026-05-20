"""Tests for confidence scorer."""

import pytest

from agentliar.checks.base import CheckResult
from agentliar.config import Settings
from agentliar.scorer import ConfidenceScore, ConfidenceScorer


class TestConfidenceScorer:
    """Test ConfidenceScorer class."""

    @pytest.fixture
    def scorer(self) -> ConfidenceScorer:
        """Create a ConfidenceScorer instance."""
        return ConfidenceScorer()

    @pytest.fixture
    def perfect_results(self) -> dict[str, CheckResult]:
        """Create perfect check results."""
        return {
            "file_check": CheckResult(
                check_name="file_check",
                passed=True,
                score=1.0,
                message="All good",
            ),
            "test_check": CheckResult(
                check_name="test_check",
                passed=True,
                score=1.0,
                message="All good",
            ),
            "scope_check": CheckResult(
                check_name="scope_check",
                passed=True,
                score=1.0,
                message="All good",
            ),
            "llm_judge": CheckResult(
                check_name="llm_judge",
                passed=True,
                score=1.0,
                message="All good",
            ),
        }

    @pytest.fixture
    def failed_results(self) -> dict[str, CheckResult]:
        """Create failed check results."""
        return {
            "file_check": CheckResult(
                check_name="file_check",
                passed=False,
                score=0.0,
                message="Failed",
            ),
            "test_check": CheckResult(
                check_name="test_check",
                passed=False,
                score=0.0,
                message="Failed",
            ),
            "scope_check": CheckResult(
                check_name="scope_check",
                passed=False,
                score=0.0,
                message="Failed",
            ),
            "llm_judge": CheckResult(
                check_name="llm_judge",
                passed=False,
                score=0.0,
                message="Failed",
            ),
        }

    def test_perfect_score(self, scorer: ConfidenceScorer, perfect_results: dict[str, CheckResult]) -> None:
        """Test perfect score calculation."""
        result = scorer.calculate(perfect_results)

        assert isinstance(result, ConfidenceScore)
        assert result.score == 100.0
        assert result.passed
        assert result.confidence_level == "high"

    def test_zero_score(self, scorer: ConfidenceScorer, failed_results: dict[str, CheckResult]) -> None:
        """Test zero score calculation."""
        result = scorer.calculate(failed_results)

        assert result.score == 0.0
        assert not result.passed
        assert result.confidence_level == "critical"

    def test_partial_score(self, scorer: ConfidenceScorer) -> None:
        """Test partial score calculation."""
        results = {
            "file_check": CheckResult(
                check_name="file_check",
                passed=True,
                score=1.0,
                message="Good",
            ),
            "test_check": CheckResult(
                check_name="test_check",
                passed=False,
                score=0.0,
                message="Bad",
            ),
            "scope_check": CheckResult(
                check_name="scope_check",
                passed=True,
                score=0.5,
                message="OK",
            ),
            "llm_judge": CheckResult(
                check_name="llm_judge",
                passed=True,
                score=1.0,
                message="Good",
            ),
        }

        result = scorer.calculate(results)

        # Score should be between 0 and 100
        assert 0 < result.score < 100

    def test_custom_weights(self, perfect_results: dict[str, CheckResult]) -> None:
        """Test custom weight calculation."""
        settings = Settings(
            file_check_weight=0.5,
            test_check_weight=0.3,
            scope_check_weight=0.1,
            llm_judge_weight=0.1,
        )
        scorer = ConfidenceScorer(settings)

        result = scorer.calculate(perfect_results)

        assert result.score == 100.0

    def test_breakdown(self, scorer: ConfidenceScorer, perfect_results: dict[str, CheckResult]) -> None:
        """Test score breakdown."""
        result = scorer.calculate(perfect_results)

        assert "file_check" in result.breakdown
        assert "test_check" in result.breakdown
        assert "scope_check" in result.breakdown
        assert "llm_judge" in result.breakdown

        for _check_name, details in result.breakdown.items():
            assert "raw_score" in details
            assert "weight" in details
            assert "contribution" in details

    def test_recommendations(self, scorer: ConfidenceScorer, failed_results: dict[str, CheckResult]) -> None:
        """Test recommendations generation."""
        result = scorer.calculate(failed_results)

        assert len(result.recommendations) > 0

    def test_explain_score(self, scorer: ConfidenceScorer, perfect_results: dict[str, CheckResult]) -> None:
        """Test score explanation."""
        result = scorer.calculate(perfect_results)
        explanation = scorer.explain_score(result)

        assert "Confidence Score" in explanation
        assert str(result.score) in explanation


class TestConfidenceLevel:
    """Test confidence level determination."""

    @pytest.fixture
    def scorer(self) -> ConfidenceScorer:
        return ConfidenceScorer()

    def test_critical_level(self, scorer: ConfidenceScorer) -> None:
        """Test critical level (0-30)."""
        results = {
            "file_check": CheckResult("file_check", False, 0.0, ""),
            "test_check": CheckResult("test_check", False, 0.0, ""),
            "scope_check": CheckResult("scope_check", False, 0.0, ""),
            "llm_judge": CheckResult("llm_judge", False, 0.0, ""),
        }
        result = scorer.calculate(results)
        assert result.confidence_level == "critical"

    def test_low_level(self, scorer: ConfidenceScorer) -> None:
        """Test low level (30-50)."""
        results = {
            "file_check": CheckResult("file_check", False, 0.4, ""),
            "test_check": CheckResult("test_check", False, 0.4, ""),
            "scope_check": CheckResult("scope_check", False, 0.4, ""),
            "llm_judge": CheckResult("llm_judge", False, 0.4, ""),
        }
        result = scorer.calculate(results)
        assert result.confidence_level == "low"

    def test_medium_level(self, scorer: ConfidenceScorer) -> None:
        """Test medium level (50-70)."""
        results = {
            "file_check": CheckResult("file_check", True, 0.6, ""),
            "test_check": CheckResult("test_check", True, 0.6, ""),
            "scope_check": CheckResult("scope_check", True, 0.6, ""),
            "llm_judge": CheckResult("llm_judge", True, 0.6, ""),
        }
        result = scorer.calculate(results)
        assert result.confidence_level == "medium"

    def test_high_level(self, scorer: ConfidenceScorer) -> None:
        """Test high level (70-100)."""
        results = {
            "file_check": CheckResult("file_check", True, 0.8, ""),
            "test_check": CheckResult("test_check", True, 0.8, ""),
            "scope_check": CheckResult("scope_check", True, 0.8, ""),
            "llm_judge": CheckResult("llm_judge", True, 0.8, ""),
        }
        result = scorer.calculate(results)
        assert result.confidence_level == "high"


class TestConfidenceScore:
    """Test ConfidenceScore dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        score = ConfidenceScore(
            score=75.0,
            passed=True,
            confidence_level="high",
            breakdown={},
            summary="Test",
            recommendations=["Rec 1"],
        )

        d = score.to_dict()

        assert d["score"] == 75.0
        assert d["passed"] is True
        assert d["confidence_level"] == "high"
        assert d["recommendations"] == ["Rec 1"]
