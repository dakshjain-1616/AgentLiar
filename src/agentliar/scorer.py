"""Confidence scorer - calculates weighted confidence score from check results."""

from dataclasses import dataclass, field
from typing import Any

from agentliar.checks.base import CheckResult
from agentliar.config import Settings, get_settings
from agentliar.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ConfidenceScore:
    """Result of confidence scoring."""

    score: float  # 0-100
    passed: bool
    confidence_level: str  # "high", "medium", "low", "critical"
    breakdown: dict[str, dict[str, Any]]
    summary: str
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "passed": self.passed,
            "confidence_level": self.confidence_level,
            "breakdown": self.breakdown,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


class ConfidenceScorer:
    """Calculates weighted confidence score from verification results."""

    # Confidence level thresholds
    LEVELS = {
        "critical": (0, 30),
        "low": (30, 50),
        "medium": (50, 70),
        "high": (70, 100),
    }

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the confidence scorer.

        Args:
            settings: Optional settings instance. Uses default if not provided.
        """
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)

    def calculate(
        self,
        results: dict[str, CheckResult],
        custom_weights: dict[str, float] | None = None,
    ) -> ConfidenceScore:
        """Calculate confidence score from check results.

        Args:
            results: Dictionary of check results by name
            custom_weights: Optional custom weights (uses settings if not provided)

        Returns:
            ConfidenceScore with calculated score and analysis
        """
        self.logger.info(
            "calculating_confidence_score",
            check_count=len(results),
        )

        # Get weights
        weights = custom_weights or self._get_weights()

        # Validate weights
        total_weight = sum(weights.values())
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero")

        # Normalize weights if they don't sum to 1
        if abs(total_weight - 1.0) > 0.001:
            weights = {k: v / total_weight for k, v in weights.items()}

        # Calculate weighted score
        weighted_sum = 0.0
        breakdown = {}

        for check_name, result in results.items():
            weight = weights.get(check_name, 0.0)
            contribution = result.score * weight * 100  # Convert to 0-100 scale
            weighted_sum += contribution

            breakdown[check_name] = {
                "raw_score": result.score,
                "weight": weight,
                "contribution": contribution,
                "passed": result.passed,
                "message": result.message,
            }

        # Final score
        final_score = min(100.0, max(0.0, weighted_sum))

        # Determine confidence level
        confidence_level = self._get_confidence_level(final_score)

        # Determine if passed
        passed = final_score >= self.settings.confidence_threshold

        # Generate summary
        summary = self._generate_summary(final_score, passed, results, breakdown)

        # Generate recommendations
        recommendations = self._generate_recommendations(final_score, results, breakdown)

        score_result = ConfidenceScore(
            score=round(final_score, 2),
            passed=passed,
            confidence_level=confidence_level,
            breakdown=breakdown,
            summary=summary,
            recommendations=recommendations,
        )

        self.logger.info(
            "confidence_score_calculated",
            score=final_score,
            passed=passed,
            level=confidence_level,
        )

        return score_result

    def _get_weights(self) -> dict[str, float]:
        """Get weights from settings."""
        return {
            "file_check": self.settings.file_check_weight,
            "test_check": self.settings.test_check_weight,
            "scope_check": self.settings.scope_check_weight,
            "llm_judge": self.settings.llm_judge_weight,
        }

    def _get_confidence_level(self, score: float) -> str:
        """Determine confidence level from score."""
        for level, (low, high) in self.LEVELS.items():
            if low <= score < high:
                return level
        return "high"  # Score >= 100

    def _generate_summary(
        self,
        score: float,
        passed: bool,
        results: dict[str, CheckResult],
        breakdown: dict[str, dict[str, Any]],
    ) -> str:
        """Generate a human-readable summary."""
        parts = []

        # Overall assessment
        if score >= 90:
            parts.append("Excellent confidence - task appears fully completed")
        elif score >= 70:
            parts.append("Good confidence - task likely completed with minor issues")
        elif score >= 50:
            parts.append("Moderate confidence - task partially completed")
        elif score >= 30:
            parts.append("Low confidence - significant issues detected")
        else:
            parts.append("Critical - task likely not completed")

        # Check-specific highlights
        failed_checks = [
            name for name, result in results.items()
            if not result.passed
        ]
        if failed_checks:
            parts.append(f"Failed checks: {', '.join(failed_checks)}")

        # Weight contributions
        top_contributor = max(
            breakdown.items(),
            key=lambda x: x[1]["contribution"],
        )
        bottom_contributor = min(
            breakdown.items(),
            key=lambda x: x[1]["contribution"],
        )

        parts.append(
            f"Strongest area: {top_contributor[0]} "
            f"({top_contributor[1]['contribution']:.1f} points)"
        )
        parts.append(
            f"Weakest area: {bottom_contributor[0]} "
            f"({bottom_contributor[1]['contribution']:.1f} points)"
        )

        return "; ".join(parts)

    def _generate_recommendations(
        self,
        score: float,
        results: dict[str, CheckResult],
        breakdown: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Generate recommendations based on results."""
        recommendations = []

        # Score-based recommendations
        if score < 30:
            recommendations.append(
                "CRITICAL: Task completion is highly questionable. "
                "Review all changes and requirements."
            )
        elif score < 50:
            recommendations.append(
                "Task appears incomplete. Address failed checks before proceeding."
            )
        elif score < 70:
            recommendations.append(
                "Task mostly complete but has issues. Review flagged items."
            )
        elif score < 90:
            recommendations.append(
                "Task appears complete with minor concerns. Consider review."
            )

        # Check-specific recommendations
        for check_name, result in results.items():
            if not result.passed:
                if check_name == "file_check":
                    recommendations.append(
                        "File Check: Ensure all expected files are present and "
                        "contain meaningful content (not placeholders)."
                    )
                elif check_name == "test_check":
                    recommendations.append(
                        "Test Check: Add real assertions to tests. "
                        "Avoid empty test bodies or trivial passes."
                    )
                elif check_name == "scope_check":
                        recommendations.append(
                            "Scope Check: Ensure all task requirements are addressed. "
                            "Avoid silent scope reduction."
                        )
                elif check_name == "llm_judge":
                    recommendations.append(
                        "LLM Judge: Independent review flagged concerns. "
                        "Review the detailed assessment."
                    )

        # Weight-based recommendations
        weights = self._get_weights()
        for check_name, weight in weights.items():
            if weight > 0.4 and not results.get(check_name, CheckResult(
                check_name=check_name, passed=True, score=0.5, message=""
            )).passed:
                recommendations.append(
                    f"{check_name} has high weight ({weight:.0%}) but failed - "
                    "this significantly impacts overall score"
                )

        return recommendations[:5]  # Limit to top 5

    def explain_score(
        self,
        score: ConfidenceScore,
        verbose: bool = False,
    ) -> str:
        """Generate a detailed explanation of the score.

        Args:
            score: The confidence score to explain
            verbose: Whether to include detailed breakdown

        Returns:
            Human-readable explanation
        """
        lines = [
            f"Confidence Score: {score.score}/100",
            f"Status: {'PASSED' if score.passed else 'FAILED'}",
            f"Level: {score.confidence_level.upper()}",
            "",
            "Summary:",
            score.summary,
        ]

        if verbose:
            lines.extend([
                "",
                "Score Breakdown:",
            ])
            for check_name, details in score.breakdown.items():
                lines.append(
                    f"  {check_name}: {details['raw_score']:.2f} "
                    f"(weight: {details['weight']:.0%}, "
                    f"contribution: {details['contribution']:.1f})"
                )

        if score.recommendations:
            lines.extend([
                "",
                "Recommendations:",
            ])
            for i, rec in enumerate(score.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        return "\n".join(lines)
