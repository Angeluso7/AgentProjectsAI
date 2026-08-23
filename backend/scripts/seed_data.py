# Wrapper to expose the seed_database function for tests when running from the backend directory.
# This ensures that `from scripts.seed_data import seed_database` works while keeping the
# actual implementation in the top‑level `scripts/seed_data.py` module.

import os
import sys

# Add the project root (two levels up from this file) to sys.path so that the top‑level
# `scripts` package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import importlib.util

# Load the top-level seed_data module without causing circular import
seed_path = os.path.join(project_root, "scripts", "seed_data.py")
spec = importlib.util.spec_from_file_location("top_level_seed_data", seed_path)
seed_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(seed_module)
seed_database = seed_module.seed_database

__all__ = ["seed_database"]
