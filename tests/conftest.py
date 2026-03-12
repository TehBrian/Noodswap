from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def temp_db_path() -> Iterator[Path]:
    """Provide an isolated sqlite path while restoring the global DB path afterward."""
    from bot import storage

    original_db_path = storage.DB_PATH
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "pytest.db"
        storage.DB_PATH = test_db_path
        storage.init_db()
        yield test_db_path
    storage.DB_PATH = original_db_path
