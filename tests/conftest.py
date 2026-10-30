import os
from pathlib import Path

# Tests run against a throwaway SQLite file and the mock manifest; set before the app is imported.
TEST_DB = Path(__file__).resolve().parent.parent / "test.db"
TEST_DB.unlink(missing_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite+aiosqlite:///{TEST_DB}",
    MANIFEST_PROVIDER="mock",
    ROBOT_API_KEYS="test-key",
)
