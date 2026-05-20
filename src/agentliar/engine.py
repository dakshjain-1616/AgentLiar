"""Verification engine - orchestrates all verification checks."""

import asyncio
from typing import Any, cast

from agentliar.checks import FileCheck, LLMJudge, ScopeCheck, TestCheck
from agentliar.checks.base import CheckResult
from agentliar.config import Settings, get_settings
from agentliar.exceptions import VerificationError
from agentliar.logging_config import get_logger

logger = get_logger(__name__)


class VerificationEngine:
    """Orchestrates all verification checks and aggregates results."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the verification engine.

        Args:
            settings: Optional settings instance. Uses default if not provided.
        """
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)

        # Initialize all checks
        self.checks = {
            "file_check": FileCheck(),
            "test_check": TestCheck(),
            "scope_check": ScopeCheck(),
            "llm_judge": LLMJudge(),
        }

        self.logger.info(
            "verification_engine_initialized",
            checks=list(self.checks.keys()),
        )

    async def verify(
        self,
        task_description: str,
        claim: dict[str, Any],
        file_changes: dict[str, Any],
        enabled_checks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run all verification checks and return aggregated results.

        Args:
            task_description: Original task description
            claim: Agent's claim about task completion
            file_changes: Dictionary of file changes made
            enabled_checks: Optional list of check names to run (runs all if None)

        Returns:
            Dictionary containing:
            - results: Dict of check results by name
            - all_passed: Whether all checks passed
            - issues: List of issues found
        """
        self.logger.info(
            "verification_started",
            task_length=len(task_description),
            claim_keys=list(claim.keys()),
            file_count=len(file_changes.get("files", {})),
        )

        # Determine which checks to run
        checks_to_run = self._get_checks_to_run(enabled_checks)

        # Run checks concurrently
        results = await self._run_checks(
            checks_to_run,
            task_description,
            claim,
            file_changes,
        )

        # Aggregate results
        all_passed = all(r.passed for r in results.values())
        issues = self._collect_issues(results)

        self.logger.info(
            "verification_completed",
            all_passed=all_passed,
            check_count=len(results),
            issue_count=len(issues),
        )

        return {
            "results": {name: result.to_dict() for name, result in results.items()},
            "all_passed": all_passed,
            "issues": issues,
            "summary": {
                "total_checks": len(results),
                "passed_checks": sum(1 for r in results.values() if r.passed),
                "failed_checks": sum(1 for r in results.values() if not r.passed),
            },
        }

    def _get_checks_to_run(
        self,
        enabled_checks: list[str] | None,
    ) -> dict[str, Any]:
        """Get the checks to run based on enabled_checks parameter."""
        if enabled_checks is None:
            return self.checks

        return {
            name: check
            for name, check in self.checks.items()
            if name in enabled_checks
        }

    async def _run_checks(
        self,
        checks: dict[str, Any],
        task_description: str,
        claim: dict[str, Any],
        file_changes: dict[str, Any],
    ) -> dict[str, CheckResult]:
        """Run all checks concurrently with error handling."""
        tasks = []
        check_names = []

        for name, check in checks.items():
            task = asyncio.create_task(
                self._run_single_check(name, check, task_description, claim, file_changes),
                name=name,
            )
            tasks.append(task)
            check_names.append(name)

        # Wait for all checks to complete
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, CheckResult] = {}
        for name, result in zip(check_names, completed_results, strict=False):
            if isinstance(result, Exception):
                # Convert exception to failed result
                self.logger.error(
                    "check_failed_with_exception",
                    check_name=name,
                    error=str(result),
                )
                results[name] = CheckResult(
                    check_name=name,
                    passed=False,
                    score=0.0,
                    message=f"Check failed with error: {result}",
                    details={"error": str(result), "error_type": type(result).__name__},
                    evidence=[str(result)],
                )
            else:
                results[name] = cast(CheckResult, result)

        return results

    async def _run_single_check(
        self,
        name: str,
        check: Any,
        task_description: str,
        claim: dict[str, Any],
        file_changes: dict[str, Any],
    ) -> CheckResult:
        """Run a single check with error handling."""
        try:
            self.logger.debug("check_started", check_name=name)
            result = cast(CheckResult, await check.run(task_description, claim, file_changes))
            self.logger.debug(
                "check_completed",
                check_name=name,
                passed=result.passed,
                score=result.score,
            )
            return result
        except Exception as e:
            self.logger.error(
                "check_exception",
                check_name=name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise VerificationError(
                f"Check {name} failed: {e}",
                check_name=name,
                details={"error": str(e)},
            ) from e

    def _collect_issues(self, results: dict[str, CheckResult]) -> list[dict[str, Any]]:
        """Collect all issues from check results."""
        issues = []

        for name, result in results.items():
            if not result.passed or result.score < 0.7:
                issues.append({
                    "check": name,
                    "message": result.message,
                    "score": result.score,
                    "evidence": result.evidence,
                    "details": result.details,
                })

        # Sort by severity (lowest score first)
        issues.sort(key=lambda x: float(cast(float, x["score"])))

        return issues

    def get_check_weights(self) -> dict[str, float]:
        """Get the weights for each check from settings."""
        return {
            "file_check": self.settings.file_check_weight,
            "test_check": self.settings.test_check_weight,
            "scope_check": self.settings.scope_check_weight,
            "llm_judge": self.settings.llm_judge_weight,
        }
