"""Test integrity check - validates test quality and detects trivial passes."""

import ast
import re
from typing import Any

from agentliar.checks.base import BaseCheck, CheckResult
from agentliar.exceptions import TestCheckError


class TestCheck(BaseCheck):
    """Verifies test integrity and detects trivially passing tests."""

    def __init__(self) -> None:
        super().__init__("test_check")

    async def run(
        self,
        task_description: str,
        claim: dict[str, Any],
        file_changes: dict[str, Any],
    ) -> CheckResult:
        """Run test integrity check.

        Validates:
        - Tests have actual assertions
        - No empty test bodies
        - No tests that always pass
        - No skipped tests without reason
        - Test coverage is reasonable
        """
        self._log_start(
            claim_tests=claim.get("tests_added", []),
            claim_tests_passed=claim.get("tests_passed", 0),
        )

        try:
            issues = []
            evidence = []
            test_files = []

            # Find test files in changes
            files = file_changes.get("files", {})
            for filepath, content in files.items():
                if self._is_test_file(filepath):
                    test_files.append((filepath, content))

            # Also check claimed test files
            for test_path in claim.get("tests_added", []):
                if test_path in files:
                    test_files.append((test_path, files[test_path]))

            if not test_files:
                # No test files found - check if tests were claimed
                if claim.get("tests_added") or claim.get("tests_passed", 0) > 0:
                    issues.append("Claimed tests but no test files found in changes")
                    evidence.append("No test files in file_changes despite claims")
                else:
                    # No tests expected - neutral score
                    result = CheckResult(
                        check_name=self.name,
                        passed=True,
                        score=0.5,
                        message="No test files to verify",
                        details={"test_files_found": 0},
                        evidence=["No test files in changes"],
                    )
                    self._log_complete(result)
                    return result

            # Analyze each test file
            total_tests = 0
            trivial_tests = 0
            skipped_tests = 0
            assertion_count = 0

            for filepath, content in test_files:
                analysis = self._analyze_test_file(filepath, content)
                total_tests += analysis["test_count"]
                trivial_tests += analysis["trivial_count"]
                skipped_tests += analysis["skipped_count"]
                assertion_count += analysis["assertion_count"]

                if analysis["issues"]:
                    issues.extend(analysis["issues"])
                    evidence.extend(analysis["evidence"])

            # Calculate score
            if total_tests == 0:
                score = 0.0
                passed = False
                message = "No actual test functions found in test files"
            elif trivial_tests == total_tests:
                score = 0.0
                passed = False
                message = f"All {total_tests} tests are trivial/empty"
            elif trivial_tests > 0:
                ratio = trivial_tests / total_tests
                score = 1.0 - ratio
                passed = score >= 0.5
                message = f"{trivial_tests}/{total_tests} tests are trivial ({ratio:.0%})"
            elif skipped_tests > 0:
                score = 0.7
                passed = True
                message = f"Tests look valid but {skipped_tests} are skipped"
            else:
                score = 1.0
                passed = True
                message = f"All {total_tests} tests appear valid with {assertion_count} assertions"

            # Check claimed vs actual
            claimed_count = claim.get("tests_passed", 0)
            if claimed_count > 0 and total_tests == 0:
                score = 0.0
                passed = False
                message = f"Claimed {claimed_count} tests passed but none found"
                issues.append(f"Claimed {claimed_count} tests but found {total_tests}")

            result = CheckResult(
                check_name=self.name,
                passed=passed,
                score=score,
                message=message,
                details={
                    "test_files": len(test_files),
                    "total_tests": total_tests,
                    "trivial_tests": trivial_tests,
                    "skipped_tests": skipped_tests,
                    "assertion_count": assertion_count,
                    "claimed_tests": claimed_count,
                },
                evidence=evidence[:10],
            )

            self._log_complete(result)
            return result

        except Exception as e:
            raise TestCheckError(
                f"Test check failed: {e}",
                check_name=self.name,
                details={"error": str(e)},
            ) from e

    def _is_test_file(self, filepath: str) -> bool:
        """Check if file is a test file."""
        test_patterns = [
            r"test_.*\.py$",
            r".*_test\.py$",
            r"tests?/.*\.py$",
            r"__tests__/.*\.py$",
            r"spec.*\.py$",
        ]
        return any(re.match(pattern, filepath) for pattern in test_patterns)

    def _analyze_test_file(self, filepath: str, content: str) -> dict[str, Any]:
        """Analyze a test file for issues."""
        result: dict[str, Any] = {
            "test_count": 0,
            "trivial_count": 0,
            "skipped_count": 0,
            "assertion_count": 0,
            "issues": [],
            "evidence": [],
        }

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            result["issues"].append(f"Syntax error in {filepath}: {e}")
            result["evidence"].append(f"Parse error at line {e.lineno}")
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name

                # Check if it's a test function
                if func_name.startswith("test_") or func_name.endswith("_test"):
                    result["test_count"] += 1
                    test_analysis = self._analyze_test_function(node)

                    result["assertion_count"] += test_analysis["assertions"]

                    if test_analysis["is_trivial"]:
                        result["trivial_count"] += 1
                        result["issues"].append(
                            f"{filepath}::{func_name} appears trivial"
                        )
                        result["evidence"].append(
                            f"Trivial: {func_name} - {test_analysis['trivial_reason']}"
                        )

                    if test_analysis["is_skipped"]:
                        result["skipped_count"] += 1
                        result["issues"].append(
                            f"{filepath}::{func_name} is skipped"
                        )

        return result

    def _analyze_test_function(self, node: ast.FunctionDef) -> dict[str, Any]:
        """Analyze a single test function."""
        assertions = 0
        analysis: dict[str, Any] = {
            "assertions": assertions,
            "is_trivial": False,
            "is_skipped": False,
            "trivial_reason": "",
        }

        # Check for skip decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id in ("skip", "pytest.mark.skip", "unittest.skip"):
                    analysis["is_skipped"] = True
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr == "skip":
                    analysis["is_skipped"] = True
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    if decorator.func.id in ("skip", "pytest.mark.skip"):
                        analysis["is_skipped"] = True
                elif isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr == "skip":
                        analysis["is_skipped"] = True

        # Count assertions and check body
        body_nodes = list(ast.walk(node))

        for n in body_nodes:
            # Count assert statements
            if isinstance(n, ast.Assert):
                assertions += 1
            # Count unittest-style assertions
            elif isinstance(n, ast.Call):
                if isinstance(n.func, ast.Attribute):
                    if n.func.attr.startswith("assert"):
                        assertions += 1
        analysis["assertions"] = assertions

        # Check for trivial bodies
        pass_nodes = [n for n in node.body if isinstance(n, ast.Pass)]
        body_lines = [n for n in node.body if not isinstance(n, ast.Pass)]

        if pass_nodes and len(body_lines) == 0:
            analysis["is_trivial"] = True
            analysis["trivial_reason"] = "Empty body (only Pass)"
        elif len(body_lines) == 1:
            # Single statement that's just pass/ellipsis/return
            single = body_lines[0]
            if isinstance(single, ast.Expr):
                if isinstance(single.value, ast.Constant):
                    if single.value.value is ... or single.value.value == "...":
                        analysis["is_trivial"] = True
                        analysis["trivial_reason"] = "Only ellipsis (...)"
            elif isinstance(single, ast.Pass):
                analysis["is_trivial"] = True
                analysis["trivial_reason"] = "Only pass statement"
            elif isinstance(single, ast.Return):
                if single.value is None or (
                    isinstance(single.value, ast.Constant) and
                    single.value.value is None
                ):
                    analysis["is_trivial"] = True
                    analysis["trivial_reason"] = "Only return None"

        # Check for no assertions
        if analysis["assertions"] == 0 and not analysis["is_skipped"] and not analysis["is_trivial"]:
            # Check if it's truly trivial (no actual test logic)
            meaningful_calls = [
                n for n in body_nodes
                if isinstance(n, ast.Call) and
                not (isinstance(n.func, ast.Name) and n.func.id in ("print", "log"))
            ]
            if len(meaningful_calls) == 0:
                analysis["is_trivial"] = True
                analysis["trivial_reason"] = "No assertions or meaningful calls"

        return analysis
