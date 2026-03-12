from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any

import pytest


class TestCase:
    """Minimal unittest-style assertion API backed by pytest assertions."""

    @pytest.fixture(autouse=True)
    def _lifecycle(self) -> Any:
        if hasattr(self, "setUp"):
            self.setUp()
        try:
            yield
        finally:
            if hasattr(self, "tearDown"):
                self.tearDown()

    @contextmanager
    def subTest(self, **_kwargs: Any) -> Any:
        yield

    def assertEqual(self, left: Any, right: Any, msg: str | None = None) -> None:
        assert left == right, msg or f"{left!r} != {right!r}"

    def assertNotEqual(self, left: Any, right: Any, msg: str | None = None) -> None:
        assert left != right, msg or f"{left!r} == {right!r}"

    def assertTrue(self, value: Any, msg: str | None = None) -> None:
        assert value, msg or f"Expected truthy value, got {value!r}"

    def assertFalse(self, value: Any, msg: str | None = None) -> None:
        assert not value, msg or f"Expected falsy value, got {value!r}"

    def assertIs(self, left: Any, right: Any, msg: str | None = None) -> None:
        assert left is right, msg or f"{left!r} is not {right!r}"

    def assertIsNone(self, value: Any, msg: str | None = None) -> None:
        assert value is None, msg or f"Expected None, got {value!r}"

    def assertIsNotNone(self, value: Any, msg: str | None = None) -> None:
        assert value is not None, msg or "Expected non-None value"

    def assertIsInstance(self, value: Any, expected_type: type[Any], msg: str | None = None) -> None:
        assert isinstance(value, expected_type), msg or f"{value!r} is not instance of {expected_type!r}"

    def assertIn(self, needle: Any, haystack: Any, msg: str | None = None) -> None:
        assert needle in haystack, msg or f"{needle!r} not found in {haystack!r}"

    def assertNotIn(self, needle: Any, haystack: Any, msg: str | None = None) -> None:
        assert needle not in haystack, msg or f"{needle!r} unexpectedly found in {haystack!r}"

    def assertGreater(self, left: Any, right: Any, msg: str | None = None) -> None:
        assert left > right, msg or f"{left!r} is not greater than {right!r}"

    def assertGreaterEqual(self, left: Any, right: Any, msg: str | None = None) -> None:
        assert left >= right, msg or f"{left!r} is not greater than or equal to {right!r}"

    def assertLess(self, left: Any, right: Any, msg: str | None = None) -> None:
        assert left < right, msg or f"{left!r} is not less than {right!r}"

    def assertLessEqual(self, left: Any, right: Any, msg: str | None = None) -> None:
        assert left <= right, msg or f"{left!r} is not less than or equal to {right!r}"

    def assertAlmostEqual(
        self,
        left: float,
        right: float,
        places: int = 7,
        msg: str | None = None,
    ) -> None:
        assert round(abs(left - right), places) == 0, msg or f"{left!r} != {right!r} within {places} places"

    def assertRegex(self, text: str, pattern: str, msg: str | None = None) -> None:
        assert re.search(pattern, text), msg or f"Pattern {pattern!r} did not match {text!r}"


class IsolatedAsyncioTestCase(TestCase):
    """Compatibility shell for pytest-asyncio collected async tests."""

    pass
