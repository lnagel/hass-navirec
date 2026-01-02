"""DataUpdateCoordinator for navirec with streaming support."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import (
    NavirecApiClientAuthenticationError,
    NavirecApiClientCommunicationError,
    NavirecApiClientRateLimitError,
    NavirecStreamClient,
)
from .const import LOGGER, STORAGE_KEY, STORAGE_VERSION
from .data import VehicleState, get_vehicle_id_from_state

if TYPE_CHECKING:
    from .data import NavirecConfigEntry


class NavirecCoordinator(DataUpdateCoordinator[dict[str, VehicleState]]):
    """Coordinator for Navirec data with streaming support."""

    config_entry: NavirecConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_url: str,
        api_token: str,
        account_id: str,
        account_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"Navirec {account_name}",
            # No update_interval - we use streaming
            update_interval=None,
        )
        self._api_url = api_url
        self._api_token = api_token
        self._account_id = account_id
        self._account_name = account_name
        self._stream_client: NavirecStreamClient | None = None
        self._stream_task: asyncio.Task | None = None
        self._initial_state_received = False
        self._should_stop = False

        # Vehicle states keyed by vehicle_id
        self.data: dict[str, VehicleState] = {}

        # Persistent storage for stream state
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY}_{account_id}",
        )
        self._last_updated_at: str | None = None

    @property
    def account_id(self) -> str:
        """Return the account ID."""
        return self._account_id

    @property
    def connected(self) -> bool:
        """Return whether the stream is connected."""
        return self._stream_client is not None and self._stream_client.connected

    async def async_start_streaming(self) -> None:
        """Start the streaming connection."""
        if self._stream_task is not None:
            return

        # Load stream state from persistent storage
        await self._async_load_stream_state()

        self._should_stop = False
        self._stream_task = self.hass.async_create_background_task(
            self._async_stream_loop(),
            f"navirec_stream_{self._account_id}",
        )
        LOGGER.info("Started streaming task for account %s", self._account_name)

    async def async_stop_streaming(self) -> None:
        """Stop the streaming connection."""
        self._should_stop = True

        try:
            if self._stream_client:
                await self._stream_client.async_disconnect()
        finally:
            self._stream_client = None
            if self._stream_task:
                self._stream_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._stream_task
                self._stream_task = None

        LOGGER.info("Stopped streaming task for account %s", self._account_name)

    async def _async_stream_loop(self) -> None:
        """Main streaming loop with reconnection logic."""
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(self.hass)

        while not self._should_stop:
            try:
                # Create stream client with stream state for resume
                self._stream_client = NavirecStreamClient(
                    api_url=self._api_url,
                    api_token=self._api_token,
                    session=session,
                    account_id=self._account_id,
                    initial_watermark=self._last_updated_at,
                )

                # Connect to stream
                await self._stream_client.async_connect()
                self._stream_client.reset_reconnect_delay()

                # Process events
                async for event in self._stream_client.async_iter_events():
                    if self._should_stop:
                        break
                    await self._async_handle_event(event)

            except NavirecApiClientAuthenticationError:
                LOGGER.error(
                    "Authentication failed for account %s. Check your API token.",
                    self._account_name,
                )
                # Don't retry on auth errors - wait longer
                await asyncio.sleep(300)

            except NavirecApiClientRateLimitError as err:
                LOGGER.warning(
                    "Rate limited for account %s. Waiting %d seconds.",
                    self._account_name,
                    err.retry_after,
                )
                await asyncio.sleep(err.retry_after)

            except NavirecApiClientCommunicationError as err:
                if self._should_stop:
                    break

                delay = (
                    self._stream_client.get_reconnect_delay()
                    if self._stream_client
                    else 5
                )
                LOGGER.warning(
                    "Stream connection lost for account %s: %s. "
                    "Reconnecting in %d seconds.",
                    self._account_name,
                    err,
                    delay,
                )
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break

            except Exception:
                LOGGER.exception(
                    "Unexpected error in stream for account %s", self._account_name
                )
                await asyncio.sleep(30)

            finally:
                if self._stream_client:
                    await self._stream_client.async_disconnect()

    async def _async_handle_event(self, event: dict[str, Any]) -> None:
        """Handle a stream event."""
        event_type = event.get("event")

        if event_type == "connected":
            LOGGER.debug("Stream connected for account %s", self._account_name)

        elif event_type == "vehicle_state":
            data = event.get("data", {})
            if data:
                state = VehicleState.model_validate(data)
                vehicle_id = get_vehicle_id_from_state(state)
                if vehicle_id:
                    self.data[vehicle_id] = state
                    self._async_notify_listeners()

                # Update and persist stream state
                if "updated_at" in data:
                    await self._async_update_stream_state(data["updated_at"])

        elif event_type == "initial_state_sent":
            self._initial_state_received = True
            LOGGER.debug(
                "Initial state received for account %s (%d vehicles)",
                self._account_name,
                len(self.data),
            )

        elif event_type == "heartbeat":
            LOGGER.debug("Heartbeat received for account %s", self._account_name)

        elif event_type == "disconnected":
            LOGGER.info(
                "Server requested disconnect for account %s. Will reconnect.",
                self._account_name,
            )

    @callback
    def _async_notify_listeners(self) -> None:
        """Notify all listeners that data has been updated."""
        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> dict[str, VehicleState]:
        """
        Fetch data from API.

        This is called by the parent class but we use streaming instead.
        Returns the current state data.
        """
        return self.data

    def get_vehicle_state(self, vehicle_id: str) -> VehicleState | None:
        """Get the current state for a vehicle."""
        return self.data.get(vehicle_id)

    async def _async_load_stream_state(self) -> None:
        """Load the stream state from persistent storage."""
        data = await self._store.async_load()
        if data and "last_updated_at" in data:
            self._last_updated_at = data["last_updated_at"]
            LOGGER.debug(
                "Loaded stream state for account %s: %s",
                self._account_name,
                self._last_updated_at,
            )
        else:
            LOGGER.debug("No stream state found for account %s", self._account_name)

    async def _async_update_stream_state(self, updated_at: str) -> None:
        """Update and persist the stream state."""
        if self._last_updated_at != updated_at:
            self._last_updated_at = updated_at
            await self._store.async_save({"last_updated_at": updated_at})
