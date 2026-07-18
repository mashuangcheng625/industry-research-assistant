"""Tests for the frozen portfolio baseline manifest."""
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from scripts.validate_baseline_manifest import validate_baseline  # noqa: E402


def test_frozen_baseline_manifest_matches_dataset_and_report():
    root = Path(__file__).resolve().parents[2]
    errors = validate_baseline(root, root / "reports/baseline-manifest.json")
    assert errors == []
