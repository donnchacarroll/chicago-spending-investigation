"""DuckDB connection helper for the Flask API."""

import threading
import duckdb
from backend.config import DUCKDB_PATH

_local = threading.local()
_test_con = None  # Set by test fixtures to override the connection


def get_db():
    """Return a thread-local read-only DuckDB connection."""
    if _test_con is not None:
        return _test_con
    if not hasattr(_local, "con") or _local.con is None:
        _local.con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    return _local.con
