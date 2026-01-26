"""Tests for Navirec constants."""

from __future__ import annotations

import json
import re
from pathlib import Path

from custom_components.navirec.const import USER_AGENT, VERSION


def test_version_matches_manifest() -> None:
    """Test that VERSION constant matches manifest.json."""
    manifest_path = (
        Path(__file__).parent.parent / "custom_components/navirec/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())

    assert manifest["version"] == VERSION


def test_user_agent_includes_version() -> None:
    """Test that USER_AGENT includes the version number."""
    assert f"hass-navirec/{VERSION}" == USER_AGENT


def test_user_agent_format() -> None:
    """Test that USER_AGENT has correct format (name/version)."""
    # Should match pattern: hass-navirec/X.Y.Z
    pattern = r"^hass-navirec/\d+\.\d+\.\d+$"
    assert re.match(pattern, USER_AGENT), (
        f"USER_AGENT '{USER_AGENT}' doesn't match expected format"
    )
