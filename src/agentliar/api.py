"""Public Python API for AgentLiar Detector."""

from typing import Any

from agentliar.checks.base import CheckResult
from agentliar.config import Settings, get_settings
from agentliar.engine import VerificationEngine
from agentliar.report import ReportGenerator, VerificationReport, create_report
from agentliar.scorer import ConfidenceScore, ConfidenceScorer


class Verifier:
    """Main API class for AgentLiar verification.

    This is the primary interface for using AgentLiar as a library.

    Example:
        >>> from agentliar import Verifier
        >>> verifier = Verifier()
        >>> result = await verifier.verify(
        ...     task_description="Implement feature X",
        ...     claim={"summary": "Done", "files_modified": ["x.py"]},
        ...     file_changes={"files": {"x.py": "code"}}
        ... )
        >>> print(result.confidence_score)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the verifier.

        Args:
            settings: Optional custom settings. Uses defaults if not provided.
        """
        self.settings = settings or get_settings()
        self._engine = VerificationEngine(self.settings)
        self._scorer = ConfidenceScorer(self.settings)

    async def verify(
        self,
        task_description: str,
        claim: dict[str, Any],
        file_changes: dict[str, Any] | None = None,
        enabled_checks: list[str] | None = None,
    ) -> "VerificationResult":
        """Verify a task completion claim.

        Args:
            task_description: Original task description
            claim: Agent's claim about task completion
            file_changes: Optional dictionary of file changes made
            enabled_checks: Optional list of check names to run

        Returns:
            VerificationResult containing all check results and confidence score

        Raises:
            AgentLiarError: If verification fails
        """
        # Default empty file_changes
        if file_changes is None:
            file_changes = {"files": {}}

        # Run verification
        verification_results = await self._engine.verify(
            task_description=task_description,
            claim=claim,
            file_changes=file_changes,
            enabled_checks=enabled_checks,
        )

        # Convert dict results to CheckResult objects
        check_results = self._dict_to_check_results(verification_results["results"])

        # Calculate confidence score
        confidence_score = self._scorer.calculate(check_results)

        # Create report
        report = create_report(
            task_description=task_description,
            claim=claim,
            check_results=check_results,
            confidence_score=confidence_score,
            metadata={
                "version": "0.1.0",
                "enabled_checks": enabled_checks or ["all"],
            },
        )

        return VerificationResult(
            report=report,
            check_results=check_results,
            confidence_score=confidence_score,
            all_passed=verification_results["all_passed"],
            issues=verification_results["issues"],
        )

    def _dict_to_check_results(
        self,
        results: dict[str, dict[str, Any]]
    ) -> dict[str, CheckResult]:
        """Convert dictionary results to CheckResult objects."""
        return {
            name: CheckResult(
                check_name=r["check_name"],
                passed=r["passed"],
                score=r["score"],
                message=r["message"],
                details=r.get("details", {}),
                evidence=r.get("evidence", []),
            )
            for name, r in results.items()
        }

    @property
    def available_checks(self) -> list[str]:
        """List of available check names."""
        return ["file_check", "test_check", "scope_check", "llm_judge"]

    def get_check_weights(self) -> dict[str, float]:
        """Get current check weights from settings."""
        return {
            "file_check": self.settings.file_check_weight,
            "test_check": self.settings.test_check_weight,
            "scope_check": self.settings.scope_check_weight,
            "llm_judge": self.settings.llm_judge_weight,
        }


class VerificationResult:
    """Result of a verification operation.

    This class provides convenient access to verification results
    and methods for generating reports.
    """

    def __init__(
        self,
        report: VerificationReport,
        check_results: dict[str, CheckResult],
        confidence_score: ConfidenceScore,
        all_passed: bool,
        issues: list[dict[str, Any]],
    ) -> None:
        self._report = report
        self.check_results = check_results
        self.confidence_score = confidence_score
        self.all_passed = all_passed
        self.issues = issues

    @property
    def passed(self) -> bool:
        """Whether the verification passed (confidence >= threshold)."""
        return self.confidence_score.passed

    @property
    def score(self) -> float:
        """The confidence score (0-100)."""
        return self.confidence_score.score

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "passed": self.passed,
            "score": self.score,
            "all_passed": self.all_passed,
            "confidence_level": self.confidence_score.confidence_level,
            "check_results": {
                name: result.to_dict()
                for name, result in self.check_results.items()
            },
            "issues": self.issues,
            "recommendations": self.confidence_score.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert result to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def generate_report(
        self,
        format: str = "markdown",
        output_path: str | None = None,
    ) -> str:
        """Generate a report in the specified format.

        Args:
            format: Report format ("json", "markdown", "console")
            output_path: Optional path to write report to

        Returns:
            Report as string
        """
        generator = ReportGenerator()

        if format == "json":
            return generator.generate_json(self._report, output_path)
        elif format == "markdown":
            return generator.generate_markdown(self._report, output_path)
        elif format == "console":
            return generator.generate_console(self._report)
        else:
            raise ValueError(f"Unknown format: {format}")

    def explain(self) -> str:
        """Get a human-readable explanation of the result."""
        scorer = ConfidenceScorer()
        return scorer.explain_score(self.confidence_score, verbose=True)

    def __repr__(self) -> str:
        return (
            f"VerificationResult("
            f"passed={self.passed}, "
            f"score={self.score:.1f}, "
            f"checks={len(self.check_results)})"
        )

    def __bool__(self) -> bool:
        """Truthiness based on whether verification passed."""
        return self.passed


# Convenience functions for simple use cases

async def verify(
    task_description: str,
    claim: dict[str, Any],
    file_changes: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> VerificationResult:
    """Quick verification function.

    Args:
        task_description: Original task description
        claim: Agent's claim about task completion
        file_changes: Optional file changes dictionary
        settings: Optional custom settings

    Returns:
        VerificationResult

    Example:
        >>> result = await verify(
        ...     "Implement feature X",
        ...     {"summary": "Done", "files_modified": ["x.py"]},
        ...     {"files": {"x.py": "code"}}
        ... )
        >>> print(result.score)
    """
    verifier = Verifier(settings)
    return await verifier.verify(task_description, claim, file_changes)


def get_version() -> str:
    """Get the AgentLiar version."""
    return "0.1.0"


def check_configuration() -> dict[str, Any]:
    """Check if AgentLiar is properly configured.

    Returns:
        Dictionary with configuration status
    """
    settings = get_settings()

    checks = {
        "openrouter_configured": bool(settings.openrouter_api_key),
        "model": settings.openrouter_model,
        "weights_valid": abs(settings.get_total_weight() - 1.0) < 0.001,
        "total_weight": settings.get_total_weight(),
    }

    checks["ready"] = (
        checks["weights_valid"]
        # LLM judge is optional, so we don't require openrouter
    )

    return checks
