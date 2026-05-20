"""Tests for scope narrowing check."""

import pytest

from agentliar.checks.scope_check import CheckResult, ScopeCheck


class TestScopeCheck:
    """Test ScopeCheck class."""

    @pytest.fixture
    def scope_check(self) -> ScopeCheck:
        """Create a ScopeCheck instance."""
        return ScopeCheck()

    @pytest.mark.asyncio
    async def test_full_completion_passes(self, scope_check: ScopeCheck) -> None:
        """Test that full task completion passes."""
        task = """Implement feature X:
1. Create main module
2. Add tests
3. Update documentation"""
        claim = {
            "summary": "Implemented feature X with main module, tests, and documentation",
            "files_modified": ["main.py", "test_main.py", "docs.md"],
        }
        changes = {"files": {
            "main.py": "def feature(): pass",
            "test_main.py": "def test_feature(): assert True",
            "docs.md": "# Feature X",
        }}

        result = await scope_check.run(task, claim, changes)

        assert isinstance(result, CheckResult)
        assert result.passed

    @pytest.mark.asyncio
    async def test_scope_narrowing_detected(self, scope_check: ScopeCheck) -> None:
        """Test detection of scope narrowing."""
        task = """Implement feature X:
1. Create main module
2. Add tests
3. Update documentation"""
        claim = {
            "summary": "Only implemented main module for now",
            "files_modified": ["main.py"],
        }
        changes = {"files": {"main.py": "def feature(): pass"}}

        result = await scope_check.run(task, claim, changes)

        assert not result.passed or result.score < 1.0
        assert any("only" in e.lower() for e in result.evidence)

    @pytest.mark.asyncio
    async def test_todo_in_files(self, scope_check: ScopeCheck) -> None:
        """Test detection of TODO in files."""
        task = "Implement feature X"
        claim = {"summary": "Task completed", "files_modified": ["main.py"]}
        changes = {"files": {"main.py": "# TODO: implement\npass"}}

        result = await scope_check.run(task, claim, changes)

        assert not result.passed or result.score < 1.0

    @pytest.mark.asyncio
    async def test_placeholder_detection(self, scope_check: ScopeCheck) -> None:
        """Test detection of placeholder implementations."""
        task = "Implement feature X"
        claim = {"summary": "Task completed", "files_modified": ["main.py"]}
        changes = {"files": {"main.py": "def feature():\n    return None"}}

        result = await scope_check.run(task, claim, changes)

        # Should detect stub return
        assert result.score < 1.0 or any("stub" in e.lower() for e in result.evidence)


class TestExtractRequirements:
    """Test requirement extraction."""

    @pytest.fixture
    def scope_check(self) -> ScopeCheck:
        return ScopeCheck()

    def test_numbered_list(self, scope_check: ScopeCheck) -> None:
        """Test extracting from numbered lists."""
        task = """1. First requirement
2. Second requirement
3. Third requirement"""
        reqs = scope_check._extract_requirements(task)

        assert len(reqs) >= 2

    def test_bullet_list(self, scope_check: ScopeCheck) -> None:
        """Test extracting from bullet lists."""
        task = """- First item
- Second item
- Third item"""
        reqs = scope_check._extract_requirements(task)

        assert len(reqs) >= 2

    def test_must_should_patterns(self, scope_check: ScopeCheck) -> None:
        """Test extracting must/should patterns."""
        task = "You must implement X. You should also add Y."
        reqs = scope_check._extract_requirements(task)

        assert any("implement" in r.lower() for r in reqs)


class TestFindScopeNarrowing:
    """Test scope narrowing detection."""

    @pytest.fixture
    def scope_check(self) -> ScopeCheck:
        return ScopeCheck()

    def test_only_keyword(self, scope_check: ScopeCheck) -> None:
        """Test 'only' keyword detection."""
        text = "I only implemented the main part"
        found = scope_check._find_scope_narrowing(text)

        assert any("only" in f.lower() for f in found)

    def test_for_now_keyword(self, scope_check: ScopeCheck) -> None:
        """Test 'for now' detection."""
        text = "This is temporary for now"
        found = scope_check._find_scope_narrowing(text)

        assert any("for now" in f.lower() for f in found)

    def test_placeholder_keyword(self, scope_check: ScopeCheck) -> None:
        """Test 'placeholder' detection."""
        text = "Added a placeholder implementation"
        found = scope_check._find_scope_narrowing(text)

        assert any("placeholder" in f.lower() for f in found)


class TestFindPartialIndicators:
    """Test partial implementation detection."""

    @pytest.fixture
    def scope_check(self) -> ScopeCheck:
        return ScopeCheck()

    def test_todo_in_content(self, scope_check: ScopeCheck) -> None:
        """Test TODO in file content."""
        changes = {"files": {"main.py": "# TODO: finish this"}}
        found = scope_check._find_partial_indicators("Task completed", changes)

        assert any("todo" in f.lower() for f in found)

    def test_not_implemented(self, scope_check: ScopeCheck) -> None:
        """Test 'not implemented' detection."""
        changes = {"files": {"main.py": "raise NotImplementedError"}}
        found = scope_check._find_partial_indicators("Task completed", changes)

        assert any("not implemented" in f.lower() for f in found)

    def test_stub_return(self, scope_check: ScopeCheck) -> None:
        """Test stub return detection."""
        changes = {"files": {"main.py": "def f():\n    return None"}}
        found = scope_check._find_partial_indicators("Task completed", changes)

        # Should detect stub patterns
        assert len(found) > 0
