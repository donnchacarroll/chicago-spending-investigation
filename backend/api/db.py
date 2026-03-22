"""DuckDB connection helper for the Flask API."""

import threading
import duckdb
from backend.config import DUCKDB_PATH

_local = threading.local()


def get_db():
    """Return a thread-local read-only DuckDB connection."""
    if not hasattr(_local, "con") or _local.con is None:
        _local.con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    return _local.con
