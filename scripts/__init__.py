"""Package to expose backend scripts at top-level for test imports.
This allows `from scripts.seed_data import seed_database` to work by importing
the actual implementation from `backend.scripts.seed_data`.
"""

from backend.scripts import seed_data  # noqa: F401
