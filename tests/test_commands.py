"""Tests for Navirec commands module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.navirec.commands import (
    _create_notification,
    _fire_result_event,
    execute_action,
)
from custom_components.navirec.models import DeviceCommand

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_device_command() -> dict:
    """Load a sample device command from fixtures."""
    with open(FIXTURES_DIR / "device_commands.json") as f:
        commands = json.load(f)
    return commands[0] if commands else {}


@pytest.fixture
def acknowledged_device_command() -> dict:
    """Load an acknowledged device command from fixtures."""
    with open(FIXTURES_DIR / "device_commands.json") as f:
        commands = json.load(f)
    return commands[1] if len(commands) > 1 else {}


@pytest.fixture
def mock_client(sample_device_command) -> MagicMock:
    """Create a mock API client."""
    client = MagicMock()
    client.async_create_device_command = AsyncMock(return_value=sample_device_command)
    client.async_get_device_command = AsyncMock(return_value=sample_device_command)
    return client


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.async_create_background_task = MagicMock()
    return hass


class TestExecuteAction:
    """Tests for execute_action function."""

    @pytest.mark.asyncio
    async def test_creates_device_command(
        self, mock_hass, mock_client, sample_device_command
    ) -> None:
        """Test that execute_action creates a device command."""
        result = await execute_action(
            hass=mock_hass,
            client=mock_client,
            vehicle_id="test-vehicle-id",
            action_id="test-action-id",
            vehicle_name="Test Vehicle",
            action_name="Test Action",
        )

        mock_client.async_create_device_command.assert_called_once_with(
            vehicle_id="test-vehicle-id",
            action_id="test-action-id",
        )
        assert isinstance(result, DeviceCommand)
        assert str(result.id) == sample_device_command["id"]

    @pytest.mark.asyncio
    async def test_spawns_background_task(
        self, mock_hass, mock_client, sample_device_command
    ) -> None:
        """Test that execute_action spawns a background polling task."""
        await execute_action(
            hass=mock_hass,
            client=mock_client,
            vehicle_id="test-vehicle-id",
            action_id="test-action-id",
            vehicle_name="Test Vehicle",
            action_name="Test Action",
        )

        mock_hass.async_create_background_task.assert_called_once()
        call_args = mock_hass.async_create_background_task.call_args
        assert f"navirec_command_{sample_device_command['id']}" in str(call_args)


class TestFireResultEvent:
    """Tests for _fire_result_event function."""

    def test_fires_event_with_correct_data(self, mock_hass) -> None:
        """Test that event is fired with correct data."""
        _fire_result_event(
            hass=mock_hass,
            command_id="test-command-id",
            state="acknowledged",
            vehicle_name="Test Vehicle",
            action_name="Test Action",
            message="test message",
            response="OK",
            errors=None,
        )

        mock_hass.bus.async_fire.assert_called_once()
        call_args = mock_hass.bus.async_fire.call_args
        assert call_args[0][0] == "navirec_command_result"
        event_data = call_args[0][1]
        assert event_data["command_id"] == "test-command-id"
        assert event_data["state"] == "acknowledged"
        assert event_data["vehicle_name"] == "Test Vehicle"
        assert event_data["action_name"] == "Test Action"
        assert event_data["response"] == "OK"


class TestCreateNotification:
    """Tests for _create_notification function."""

    def test_acknowledged_notification(self, mock_hass) -> None:
        """Test notification for acknowledged command."""
        with patch("custom_components.navirec.commands.async_create") as mock_create:
            _create_notification(
                hass=mock_hass,
                command_id="test-command-id",
                state="acknowledged",
                vehicle_name="Test Vehicle",
                action_name="Lock doors",
                response="Doors locked",
            )

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "succeeded" in call_args.kwargs["title"]
            assert "Doors locked" in call_args.kwargs["message"]

    def test_failed_notification(self, mock_hass) -> None:
        """Test notification for failed command."""
        with patch("custom_components.navirec.commands.async_create") as mock_create:
            _create_notification(
                hass=mock_hass,
                command_id="test-command-id",
                state="failed",
                vehicle_name="Test Vehicle",
                action_name="Lock doors",
                errors="Device offline",
            )

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "failed" in call_args.kwargs["title"]
            assert "Device offline" in call_args.kwargs["message"]

    def test_expired_notification(self, mock_hass) -> None:
        """Test notification for expired command."""
        with patch("custom_components.navirec.commands.async_create") as mock_create:
            _create_notification(
                hass=mock_hass,
                command_id="test-command-id",
                state="expired",
                vehicle_name="Test Vehicle",
                action_name="Lock doors",
            )

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "timed out" in call_args.kwargs["title"]
