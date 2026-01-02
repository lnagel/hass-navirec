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


class TestStreamStatePersistence:
    """Tests for stream state persistence."""

    @pytest.mark.asyncio
    async def test_load_stream_state_no_existing_data(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test loading stream state when no persisted data exists."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        # Mock Store to return None (no existing data)
        with patch.object(coordinator._store, "async_load", return_value=None):
            await coordinator._async_load_stream_state()

        assert coordinator._last_updated_at is None

    @pytest.mark.asyncio
    async def test_load_stream_state_with_existing_data(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test loading stream state from persisted storage."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        # Mock Store to return existing last_updated_at
        existing_last_updated_at = "2025-12-31T19:09:24.796730Z"
        with patch.object(
            coordinator._store,
            "async_load",
            return_value={"last_updated_at": existing_last_updated_at},
        ):
            await coordinator._async_load_stream_state()

        assert coordinator._last_updated_at == existing_last_updated_at

    @pytest.mark.asyncio
    async def test_load_stream_state_with_invalid_data(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test loading stream state when storage has invalid data."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        # Mock Store to return data without last_updated_at key
        with patch.object(
            coordinator._store, "async_load", return_value={"other_key": "value"}
        ):
            await coordinator._async_load_stream_state()

        assert coordinator._last_updated_at is None

    @pytest.mark.asyncio
    async def test_update_stream_state_saves_new_value(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test that updating stream state saves to storage."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        new_last_updated_at = "2025-12-31T19:09:24.796730Z"

        with patch.object(coordinator._store, "async_save") as mock_save:
            await coordinator._async_update_stream_state(new_last_updated_at)

        assert coordinator._last_updated_at == new_last_updated_at
        mock_save.assert_called_once_with({"last_updated_at": new_last_updated_at})

    @pytest.mark.asyncio
    async def test_update_stream_state_skips_duplicate(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test that updating stream state with same value doesn't save."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        last_updated_at = "2025-12-31T19:09:24.796730Z"
        coordinator._last_updated_at = last_updated_at

        with patch.object(coordinator._store, "async_save") as mock_save:
            await coordinator._async_update_stream_state(last_updated_at)

        # Should not save if value hasn't changed
        mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_vehicle_state_event_persists_updated_at(
        self,
        hass: HomeAssistant,
        enable_custom_integrations: None,
        vehicle_states_fixture: list[dict[str, Any]],
    ) -> None:
        """Test that vehicle_state event triggers stream state persistence."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        sample_state = vehicle_states_fixture[0]
        expected_last_updated_at = sample_state["updated_at"]

        event = {
            "event": "vehicle_state",
            "data": sample_state,
        }

        with (
            patch.object(coordinator, "_async_notify_listeners"),
            patch.object(coordinator._store, "async_save") as mock_save,
        ):
            await coordinator._async_handle_event(event)

        assert coordinator._last_updated_at == expected_last_updated_at
        mock_save.assert_called_once_with({"last_updated_at": expected_last_updated_at})

    @pytest.mark.asyncio
    async def test_vehicle_state_event_without_updated_at(
        self,
        hass: HomeAssistant,
        enable_custom_integrations: None,
    ) -> None:
        """Test that vehicle_state event without updated_at doesn't crash."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        # Event data without updated_at field
        event = {
            "event": "vehicle_state",
            "data": {
                "vehicle": "https://api.navirec.com/vehicles/test-id/",
                "speed": 50,
            },
        }

        with (
            patch.object(coordinator, "_async_notify_listeners"),
            patch.object(coordinator._store, "async_save") as mock_save,
        ):
            await coordinator._async_handle_event(event)

        # Should not save if no updated_at in data
        mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_state_loaded_on_start_streaming(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test that stream state is loaded when streaming starts."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        existing_last_updated_at = "2025-12-31T19:09:24.796730Z"

        with (
            patch.object(
                coordinator._store,
                "async_load",
                return_value={"last_updated_at": existing_last_updated_at},
            ),
            patch.object(
                coordinator, "_async_stream_loop", new_callable=AsyncMock
            ) as mock_loop,
        ):
            # Create a proper awaitable future
            future = asyncio.Future()
            future.set_result(None)
            mock_loop.return_value = future

            await coordinator.async_start_streaming()

        assert coordinator._last_updated_at == existing_last_updated_at

    @pytest.mark.asyncio
    async def test_stream_client_receives_initial_last_updated_at(
        self, hass: HomeAssistant, enable_custom_integrations: None
    ) -> None:
        """Test that stream client is created with persisted last_updated_at."""
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        existing_last_updated_at = "2025-12-31T19:09:24.796730Z"
        coordinator._last_updated_at = existing_last_updated_at

        # Test the actual instantiation without mocking
        session = async_get_clientsession(hass)
        from custom_components.navirec.api import NavirecStreamClient

        # Create the client the same way the coordinator does
        client = NavirecStreamClient(
            api_url=coordinator._api_url,
            api_token=coordinator._api_token,
            session=session,
            account_id=coordinator._account_id,
            initial_last_updated_at=coordinator._last_updated_at,
        )

        # Verify the last_updated_at was passed correctly
        assert client._last_updated_at == existing_last_updated_at
        assert client.last_updated_at == existing_last_updated_at

    @pytest.mark.asyncio
    async def test_stream_state_persists_across_multiple_events(
        self,
        hass: HomeAssistant,
        enable_custom_integrations: None,
        vehicle_states_fixture: list[dict[str, Any]],
    ) -> None:
        """Test that stream state is updated with latest last_updated_at from multiple events."""
        coordinator = NavirecCoordinator(
            hass=hass,
            api_url="https://api.navirec.com",
            api_token="test-token",
            account_id="test-account-id",
            account_name="Test Account",
        )

        # Process multiple events
        with (
            patch.object(coordinator, "_async_notify_listeners"),
            patch.object(coordinator._store, "async_save") as mock_save,
        ):
            for state in vehicle_states_fixture[:3]:
                event = {
                    "event": "vehicle_state",
                    "data": state,
                }
                await coordinator._async_handle_event(event)

        # Should have the last updated_at value
        final_last_updated_at = vehicle_states_fixture[2]["updated_at"]
        assert coordinator._last_updated_at == final_last_updated_at
        # Should have been called 3 times (once per event with different last_updated_at)
        assert mock_save.call_count == 3
