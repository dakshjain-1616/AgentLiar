"""File verification check - validates file changes against task requirements."""

import re
from typing import Any

from agentliar.checks.base import BaseCheck, CheckResult
from agentliar.exceptions import FileCheckError


class FileCheck(BaseCheck):
    """Verifies that file changes align with task requirements."""

    def __init__(self) -> None:
        super().__init__("file_check")

    async def run(
        self,
        task_description: str,
        claim: dict[str, Any],
        file_changes: dict[str, Any],
    ) -> CheckResult:
        """Run file verification check.

        Validates:
        - Expected files are present
        - No unexpected files were created
        - File content matches expectations
        - File sizes are reasonable
        """
        self._log_start(
            task_description_length=len(task_description),
            claim_files=claim.get("files_modified", []),
        )

        try:
            issues = []
            evidence = []

            # Extract expected files from task description
            expected_files = self._extract_expected_files(task_description)
            claimed_files = set(claim.get("files_modified", []))
            actual_files = set(file_changes.get("files", {}).keys())

            # Check for missing expected files
            missing_files = expected_files - actual_files
            if missing_files:
                issues.append(f"Missing expected files: {missing_files}")
                evidence.extend([f"Missing: {f}" for f in missing_files])

            # Check for unexpected files
            unexpected_files = actual_files - expected_files - claimed_files
            if unexpected_files:
                issues.append(f"Unexpected files created: {unexpected_files}")
                evidence.extend([f"Unexpected: {f}" for f in unexpected_files])

            # Validate file content
            content_issues = self._validate_file_content(file_changes)
            issues.extend(content_issues)
            evidence.extend(content_issues)

            # Check for empty or trivial files
            trivial_issues = self._check_trivial_files(file_changes)
            issues.extend(trivial_issues)
            evidence.extend(trivial_issues)

            # Calculate score
            if not issues:
                score = 1.0
                passed = True
                message = "All file changes align with task requirements"
            elif len(issues) <= 2:
                score = 0.7
                passed = True
                message = f"Minor file issues: {'; '.join(issues[:2])}"
            elif len(issues) <= 4:
                score = 0.4
                passed = False
                message = f"Significant file issues: {'; '.join(issues[:3])}"
            else:
                score = 0.0
                passed = False
                message = f"Critical file issues: {'; '.join(issues[:3])}"

            result = CheckResult(
                check_name=self.name,
                passed=passed,
                score=score,
                message=message,
                details={
                    "expected_files": list(expected_files),
                    "claimed_files": list(claimed_files),
                    "actual_files": list(actual_files),
                    "missing_files": list(missing_files),
                    "unexpected_files": list(unexpected_files),
                    "issue_count": len(issues),
                },
                evidence=evidence[:10],  # Limit evidence
            )

            self._log_complete(result)
            return result

        except Exception as e:
            raise FileCheckError(
                f"File check failed: {e}",
                check_name=self.name,
                details={"error": str(e)},
            ) from e

    def _extract_expected_files(self, task_description: str) -> set[str]:
        """Extract expected file paths from task description.

        Looks for patterns like:
        - "create file X"
        - "modify file Y"
        - "src/module/file.py"
        - file paths with extensions
        """
        expected = set()

        # Pattern: quoted or code-block file paths
        patterns = [
            r"`([^`]+\.(?:py|js|ts|json|yaml|yml|toml|md|txt|sh))`",
            r'"([^"]+\.(?:py|js|ts|json|yaml|yml|toml|md|txt|sh))"',
            r"'([^']+\.(?:py|js|ts|json|yaml|yml|toml|md|txt|sh))'",
            r"(?:create|modify|update|edit|add)\s+(?:file\s+)?([\w/]+\.(?:py|js|ts|json|yaml|yml|toml|md|txt))",
            r"((?:src|tests?|docs?|config)/[\w/]+\.(?:py|js|ts|json|yaml|yml|toml|md))",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, task_description, re.IGNORECASE)
            for match in matches:
                expected.add(match)

        return expected

    def _validate_file_content(self, file_changes: dict[str, Any]) -> list[str]:
        """Validate file content for common issues."""
        issues = []
        files = file_changes.get("files", {})

        for filepath, content in files.items():
            # Check for TODO/FIXME markers indicating incomplete work
            if isinstance(content, str):
                if "TODO" in content.upper() or "FIXME" in content.upper():
                    issues.append(f"{filepath} contains TODO/FIXME markers")

                # Check for placeholder content
                if content.strip() in ["pass", "...", "# TODO", "# FIXME", ""]:
                    issues.append(f"{filepath} contains placeholder content")

                # Check for extremely short files
                if len(content.strip()) < 20:
                    issues.append(f"{filepath} is suspiciously short ({len(content.strip())} chars)")

        return issues

    def _check_trivial_files(self, file_changes: dict[str, Any]) -> list[str]:
        """Check for trivial or empty files."""
        issues = []
        files = file_changes.get("files", {})

        for filepath, content in files.items():
            if isinstance(content, str):
                stripped = content.strip()

                # Empty or near-empty files
                if len(stripped) == 0:
                    issues.append(f"{filepath} is empty")

                # Files with only comments
                lines = stripped.split('\n')
                non_comment_lines = [
                    line for line in lines
                    if line.strip() and not line.strip().startswith('#')
                ]
                if len(non_comment_lines) == 0 and len(lines) > 1:
                    issues.append(f"{filepath} contains only comments")

        return issues
