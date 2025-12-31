"""Tests for Navirec coordinator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.navirec.coordinator import NavirecCoordinator


class TestNavirecCoordinator:
    """Tests for NavirecCoordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_init(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test coordinator initialization."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        assert coordinator.account_id == "test-account-id"
        # connected depends on _stream_client which is None initially
        assert coordinator.connected is False
        # Data dict should be empty
        assert coordinator.data == {}

    @pytest.mark.asyncio
    async def test_get_vehicle_state_empty(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test getting vehicle state when no states exist."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        result = coordinator.get_vehicle_state("nonexistent-vehicle")
        assert result is None

    @pytest.mark.asyncio
    async def test_start_streaming_creates_task(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test that start_streaming creates a background task."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        # Patch the stream loop to prevent actual execution
        with patch.object(
            coordinator, "_async_stream_loop", new_callable=AsyncMock
        ) as mock_loop:
            # Create a proper awaitable future that completes immediately
            future = asyncio.Future()
            future.set_result(None)
            mock_loop.return_value = future

            await coordinator.async_start_streaming()

            # Task should have been created
            assert coordinator._stream_task is not None

    @pytest.mark.asyncio
    async def test_stop_streaming_clears_state(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test that stop_streaming clears task and client."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        # Create a real asyncio task that we can cancel
        async def dummy_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                raise

        task = asyncio.create_task(dummy_task())
        coordinator._stream_task = task

        # Mock stream client
        mock_client = MagicMock()
        mock_client.async_disconnect = AsyncMock()
        coordinator._stream_client = mock_client

        await coordinator.async_stop_streaming()

        assert coordinator._stream_task is None
        assert coordinator._stream_client is None


class TestStreamEventHandling:
    """Tests for stream event handling."""

    @pytest.mark.asyncio
    async def test_handle_connected_event_logs(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test handling connected event (logs but doesn't change state)."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        event = {"event": "connected"}
        # Should not raise - just logs
        await coordinator._async_handle_event(event)

    @pytest.mark.asyncio
    async def test_handle_heartbeat_event(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test handling heartbeat event (should not raise)."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        event = {"event": "heartbeat"}
        # Should not raise any exception
        await coordinator._async_handle_event(event)

    @pytest.mark.asyncio
    async def test_handle_vehicle_state_event(
        self,
        hass: HomeAssistant,
        enable_custom_integrations: None,
        vehicle_states_fixture: list[dict[str, Any]],
    ) -> None:
        """Test handling vehicle_state event stores state data."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        sample_state = vehicle_states_fixture[0]
        event = {
            "event": "vehicle_state",
            "data": sample_state,
        }

        with patch.object(coordinator, "_async_notify_listeners"):
            await coordinator._async_handle_event(event)

        # Extract vehicle ID from the fixture's vehicle URL
        vehicle_url = sample_state["vehicle"]
        # URL format: https://api.../vehicles/{uuid}/
        vehicle_id = vehicle_url.split("/vehicles/")[1].rstrip("/")

        state = coordinator.get_vehicle_state(vehicle_id)
        assert state is not None
        assert state.speed == sample_state["speed"]

    @pytest.mark.asyncio
    async def test_handle_initial_state_sent_event(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test handling initial_state_sent event."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        assert coordinator._initial_state_received is False

        event = {"event": "initial_state_sent"}
        await coordinator._async_handle_event(event)

        assert coordinator._initial_state_received is True

    @pytest.mark.asyncio
    async def test_handle_disconnected_event_logs(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test handling disconnected event (logs reconnect info)."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        event = {"event": "disconnected"}
        # Should not raise - just logs
        await coordinator._async_handle_event(event)
