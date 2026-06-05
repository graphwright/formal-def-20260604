"""
conftest.py — pytest configuration for medlit graph tests.

Run against a specific JSONL directory:
    pytest --jsonl-dir /path/to/migrated/

Default: looks for ./data/migrated/ relative to the test file.
Tests that require a loaded graph are skipped if no JSONL files are found.
"""

import pytest
from pathlib import Path
from medlit_graph import MedlitGraph


def pytest_addoption(parser):
    parser.addoption(
        "--jsonl-dir",
        action="store",
        default=None,
        help="Directory containing migrated JSONL files (default: ./data/migrated/)",
    )


def _resolve_jsonl_dir(config) -> Path | None:
    explicit = config.getoption("--jsonl-dir", default=None)
    if explicit:
        return Path(explicit)
    # Fallback: conventional location relative to conftest.py
    fallback = Path(__file__).parent / "data" / "migrated"
    if fallback.exists():
        return fallback
    return None


@pytest.fixture(scope="session")
def jsonl_dir(request) -> Path:
    d = _resolve_jsonl_dir(request.config)
    if d is None or not d.exists():
        pytest.skip(
            "No JSONL directory found. "
            "Run with --jsonl-dir /path/to/data or place files in tests/data/migrated/"
        )
    jsonl_files = list(d.glob("*.jsonl"))
    if not jsonl_files:
        pytest.skip(f"No .jsonl files found in {d}")
    return d


@pytest.fixture(scope="session")
def g(jsonl_dir) -> MedlitGraph:
    """Session-scoped graph — built once, shared across all tests."""
    graph = MedlitGraph.from_jsonl_dir(jsonl_dir)
    if not graph.entities and not graph.by_predicate:
        pytest.skip("Graph is empty after loading JSONL files")
    return graph
