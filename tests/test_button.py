"""Tests for Navirec button platform."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.navirec.button import NavirecActionButton
from custom_components.navirec.models import Action, Vehicle

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_vehicle() -> dict:
    """Load a sample vehicle from fixtures."""
    with open(FIXTURES_DIR / "vehicles.json") as f:
        vehicles = json.load(f)
    return vehicles[0] if vehicles else {}


@pytest.fixture
def sample_action() -> dict:
    """Load a sample action from fixtures."""
    with open(FIXTURES_DIR / "actions.json") as f:
        actions = json.load(f)
    return actions[0] if actions else {}


@pytest.fixture
def mock_vehicle(sample_vehicle) -> Vehicle:
    """Create a Vehicle model from fixture."""
    return Vehicle.model_validate(sample_vehicle)


@pytest.fixture
def mock_action(sample_action) -> Action:
    """Create an Action model from fixture."""
    return Action.model_validate(sample_action)


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.connected = True
    return coordinator


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.runtime_data = MagicMock()
    entry.runtime_data.account_id = "test-account-id"
    entry.runtime_data.client = MagicMock()
    return entry


@pytest.fixture
def vehicle_id(sample_vehicle) -> str:
    """Extract vehicle ID from sample vehicle."""
    return sample_vehicle["id"]


class TestNavirecActionButton:
    """Tests for NavirecActionButton."""

    def test_unique_id(
        self, mock_coordinator, mock_config_entry, mock_vehicle, mock_action, vehicle_id
    ) -> None:
        """Test unique ID generation."""
        button = NavirecActionButton(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
            action=mock_action,
        )

        assert button.unique_id == f"{vehicle_id}_{mock_action.id}"

    def test_name_from_name_display(
        self, mock_coordinator, mock_config_entry, mock_vehicle, mock_action, vehicle_id
    ) -> None:
        """Test that name comes from action.name_display."""
        button = NavirecActionButton(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
            action=mock_action,
        )

        assert button.name == mock_action.name_display

    def test_enabled_by_default(
        self, mock_coordinator, mock_config_entry, mock_vehicle, mock_action, vehicle_id
    ) -> None:
        """Test that button is enabled by default."""
        button = NavirecActionButton(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
            action=mock_action,
        )

        assert button.entity_registry_enabled_default is True

    @pytest.mark.asyncio
    async def test_async_press_calls_execute_action(
        self, mock_coordinator, mock_config_entry, mock_vehicle, mock_action, vehicle_id
    ) -> None:
        """Test that pressing the button calls execute_action."""
        button = NavirecActionButton(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
            action=mock_action,
        )
        button.hass = MagicMock()

        with patch(
            "custom_components.navirec.button.execute_action", new_callable=AsyncMock
        ) as mock_execute:
            await button.async_press()

            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            assert call_args.kwargs["vehicle_id"] == vehicle_id
            assert call_args.kwargs["action_id"] == str(mock_action.id)
