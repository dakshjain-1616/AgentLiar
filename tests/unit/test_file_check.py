"""Tests for file verification check."""

from typing import Any

import pytest

from agentliar.checks.file_check import CheckResult, FileCheck


class TestFileCheck:
    """Test FileCheck class."""

    @pytest.fixture
    def file_check(self) -> FileCheck:
        """Create a FileCheck instance."""
        return FileCheck()

    @pytest.mark.asyncio
    async def test_empty_changes_pass(self, file_check: FileCheck) -> None:
        """Test that empty changes pass when no files expected."""
        task = "Simple task with no file requirements"
        claim = {"summary": "Done"}
        changes: dict[str, Any] = {"files": {}}

        result = await file_check.run(task, claim, changes)

        assert isinstance(result, CheckResult)
        assert result.passed
        assert result.score >= 0.5

    @pytest.mark.asyncio
    async def test_missing_expected_files(self, file_check: FileCheck) -> None:
        """Test detection of missing expected files."""
        task = 'Create file `src/main.py` and `src/utils.py`'
        claim = {"summary": "Done", "files_modified": ["src/main.py"]}
        changes = {"files": {"src/main.py": "print('hello')"}}

        result = await file_check.run(task, claim, changes)

        assert not result.passed or result.score < 1.0
        assert "src/utils.py" in str(result.details.get("missing_files", []))

    @pytest.mark.asyncio
    async def test_unexpected_files(self, file_check: FileCheck) -> None:
        """Test detection of unexpected files."""
        task = "Create file src/main.py"
        claim = {"summary": "Done", "files_modified": ["src/main.py"]}
        changes = {"files": {
            "src/main.py": "print('hello')",
            "src/extra.py": "print('extra')",
        }}

        result = await file_check.run(task, claim, changes)

        assert "src/extra.py" in str(result.details.get("unexpected_files", []))

    @pytest.mark.asyncio
    async def test_todo_in_content(self, file_check: FileCheck) -> None:
        """Test detection of TODO markers in content."""
        task = "Create file src/main.py"
        claim = {"summary": "Done"}
        changes = {"files": {"src/main.py": "# TODO: implement this\npass"}}

        result = await file_check.run(task, claim, changes)

        assert not result.passed or result.score < 1.0
        assert any("TODO" in e for e in result.evidence)

    @pytest.mark.asyncio
    async def test_placeholder_content(self, file_check: FileCheck) -> None:
        """Test detection of placeholder content."""
        task = "Create file src/main.py"
        claim = {"summary": "Done"}
        changes = {"files": {"src/main.py": "pass"}}

        result = await file_check.run(task, claim, changes)

        assert not result.passed or result.score < 1.0

    @pytest.mark.asyncio
    async def test_empty_file(self, file_check: FileCheck) -> None:
        """Test detection of empty files."""
        task = "Create file src/main.py"
        claim = {"summary": "Done"}
        changes = {"files": {"src/main.py": ""}}

        result = await file_check.run(task, claim, changes)

        assert not result.passed
        assert any("empty" in e.lower() for e in result.evidence)

    @pytest.mark.asyncio
    async def test_valid_files_pass(self, file_check: FileCheck) -> None:
        """Test that valid files pass."""
        task = "Create file src/main.py"
        claim = {"summary": "Done", "files_modified": ["src/main.py"]}
        changes = {"files": {"src/main.py": "def main():\n    print('hello')\n    return 42"}}

        result = await file_check.run(task, claim, changes)

        assert result.passed
        assert result.score == 1.0


class TestExtractExpectedFiles:
    """Test file extraction from task descriptions."""

    @pytest.fixture
    def file_check(self) -> FileCheck:
        return FileCheck()

    def test_extract_quoted_files(self, file_check: FileCheck) -> None:
        """Test extracting quoted file paths."""
        task = 'Create `src/main.py` and `src/utils.py`'
        files = file_check._extract_expected_files(task)

        assert "src/main.py" in files
        assert "src/utils.py" in files

    def test_extract_code_block_files(self, file_check: FileCheck) -> None:
        """Test extracting files from code blocks."""
        task = 'Create "config.json" and "settings.yaml"'
        files = file_check._extract_expected_files(task)

        assert "config.json" in files
        assert "settings.yaml" in files

    def test_extract_create_patterns(self, file_check: FileCheck) -> None:
        """Test extracting from 'create file' patterns."""
        task = "Create file src/app.py with main function"
        files = file_check._extract_expected_files(task)

        assert "src/app.py" in files

    def test_extract_path_patterns(self, file_check: FileCheck) -> None:
        """Test extracting path-like patterns."""
        task = "Update src/module/utils.py and tests/test_utils.py"
        files = file_check._extract_expected_files(task)

        assert "src/module/utils.py" in files or "tests/test_utils.py" in files


class TestValidateFileContent:
    """Test file content validation."""

    @pytest.fixture
    def file_check(self) -> FileCheck:
        return FileCheck()

    def test_todo_detection(self, file_check: FileCheck) -> None:
        """Test TODO detection."""
        changes = {"files": {"test.py": "# TODO: fix this\npass"}}
        issues = file_check._validate_file_content(changes)

        assert any("TODO" in i for i in issues)

    def test_fixme_detection(self, file_check: FileCheck) -> None:
        """Test FIXME detection."""
        changes = {"files": {"test.py": "# FIXME: implement\npass"}}
        issues = file_check._validate_file_content(changes)

        assert any("FIXME" in i for i in issues)

    def test_placeholder_detection(self, file_check: FileCheck) -> None:
        """Test placeholder detection."""
        changes = {"files": {"test.py": "pass"}}
        issues = file_check._validate_file_content(changes)

        assert any("placeholder" in i.lower() for i in issues)

    def test_short_file_detection(self, file_check: FileCheck) -> None:
        """Test short file detection."""
        changes = {"files": {"test.py": "x"}}
        issues = file_check._validate_file_content(changes)

        assert any("short" in i.lower() for i in issues)


class TestCheckTrivialFiles:
    """Test trivial file detection."""

    @pytest.fixture
    def file_check(self) -> FileCheck:
        return FileCheck()

    def test_empty_file(self, file_check: FileCheck) -> None:
        """Test empty file detection."""
        changes = {"files": {"test.py": ""}}
        issues = file_check._check_trivial_files(changes)

        assert any("empty" in i.lower() for i in issues)

    def test_comment_only_file(self, file_check: FileCheck) -> None:
        """Test comment-only file detection."""
        changes = {"files": {"test.py": "# comment\n# another"}}
        issues = file_check._check_trivial_files(changes)

        assert any("comment" in i.lower() for i in issues)
