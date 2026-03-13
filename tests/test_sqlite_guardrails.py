import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_SQLITE_WITH_PATTERN = re.compile(r"with\s+sqlite3\.connect\([^\)]*\)\s+as\s+conn\s*:")


def test_no_raw_sqlite_connection_contexts() -> None:
    python_files = list(REPO_ROOT.rglob("*.py"))
    violations: list[str] = []
    current_test_file = Path(__file__).resolve()

    for file_path in python_files:
        if file_path.resolve() == current_test_file:
            continue
        relative_path = file_path.relative_to(REPO_ROOT)
        if "__pycache__" in relative_path.parts:
            continue

        content = file_path.read_text(encoding="utf-8")
        if RAW_SQLITE_WITH_PATTERN.search(content):
            violations.append(str(relative_path))

    assert violations == [], (
        "Avoid `with sqlite3.connect(...) as conn:`. Use explicit close patterns (e.g. contextlib.closing) so handles are always closed."
    )
