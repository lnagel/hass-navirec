"""Navirec API Client."""

from __future__ import annotations

import asyncio
import json
import re
import socket
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import (
    API_REQUEST_TIMEOUT,
    API_VERSION,
    DEFAULT_RETRY_AFTER,
    LOGGER,
    STREAM_CONNECT_TIMEOUT,
    STREAM_READ_TIMEOUT,
    STREAM_RECONNECT_MAX_DELAY,
    STREAM_RECONNECT_MIN_DELAY,
    STREAM_RECONNECT_MULTIPLIER,
    USER_AGENT,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping


class NavirecApiClientError(Exception):
    """Exception to indicate a general API error."""


class NavirecApiClientCommunicationError(NavirecApiClientError):
    """Exception to indicate a communication error."""


class NavirecApiClientAuthenticationError(NavirecApiClientError):
    """Exception to indicate an authentication error."""


class NavirecApiClientRateLimitError(NavirecApiClientError):
    """Exception to indicate rate limiting."""

    def __init__(self, message: str, retry_after: int = DEFAULT_RETRY_AFTER) -> None:
        """Initialize rate limit error."""
        super().__init__(message)
        self.retry_after = retry_after


def parse_retry_after(value: str | None) -> int:
    """
    Parse a Retry-After header value into seconds.

    Only the delay-seconds form is supported. Missing, malformed (e.g. the
    HTTP-date form) or negative values fall back to DEFAULT_RETRY_AFTER.
    """
    try:
        seconds = int(value) if value is not None else DEFAULT_RETRY_AFTER
    except ValueError:
        return DEFAULT_RETRY_AFTER
    return seconds if seconds >= 0 else DEFAULT_RETRY_AFTER


class NavirecApiClient:
    """Navirec API Client for REST endpoints."""

    def __init__(
        self,
        api_url: str,
        api_token: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._api_url = api_url.rstrip("/")
        self._api_token = api_token
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        """Get common headers for API requests."""
        return {
            "Authorization": f"Token {self._api_token}",
            "Accept": f"application/json; version={API_VERSION}",
            "User-Agent": USER_AGENT,
        }

    async def async_validate_token(self) -> bool:
        """Validate the API token by fetching accounts."""
        try:
            accounts = await self.async_get_accounts()
            return len(accounts) > 0
        except NavirecApiClientAuthenticationError:
            return False

    async def async_get_accounts(self) -> list[dict[str, Any]]:
        """
        Get accounts accessible by the token.

        Note: This intentionally fetches only the first page since API tokens
        typically have access to just one account, and we only need to find
        that account's ID and name.
        """
        data, _ = await self._async_request_json("GET", f"{self._api_url}/accounts/")
        return data

    async def async_get_vehicles(
        self, account_id: str | None = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Get vehicles, optionally filtered by account."""
        params = []
        if account_id:
            params.append(f"account={account_id}")
        if active_only:
            params.append("active=true")

        url = f"{self._api_url}/vehicles/"
        if params:
            url = f"{url}?{'&'.join(params)}"

        return await self._async_get_paginated(url)

    async def async_get_sensors(
        self, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get sensors, optionally filtered by account."""
        url = f"{self._api_url}/sensors/"
        if account_id:
            url = f"{url}?account={account_id}"
        return await self._async_get_paginated(url)

    async def async_get_interpretations(self) -> list[dict[str, Any]]:
        """Get all interpretations (sensor metadata)."""
        url = f"{self._api_url}/interpretations/"
        return await self._async_get_paginated(url)

    async def async_get_actions(
        self, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get actions, optionally filtered by account."""
        url = f"{self._api_url}/actions/"
        if account_id:
            url = f"{url}?account={account_id}"
        return await self._async_get_paginated(url)

    async def async_create_device_command(
        self,
        vehicle_id: str,
        action_id: str,
    ) -> dict[str, Any]:
        """
        Create a device command to execute an action.

        Args:
            vehicle_id: The UUID of the target vehicle.
            action_id: The UUID of the action to execute.

        Returns:
            The created DeviceCommand object from the API.

        """
        vehicle_url = f"{self._api_url}/vehicles/{vehicle_id}/"
        action_url = f"{self._api_url}/actions/{action_id}/"

        data, _ = await self._async_request_json(
            "POST",
            f"{self._api_url}/device_commands/",
            json={"vehicle": vehicle_url, "action": action_url},
        )
        return data

    async def async_get_device_command(self, command_id: str) -> dict[str, Any]:
        """Get a device command by ID."""
        data, _ = await self._async_request_json(
            "GET",
            f"{self._api_url}/device_commands/{command_id}/",
        )
        return data

    async def _async_get_paginated(self, url: str) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated endpoint."""
        results: list[dict[str, Any]] = []
        next_url: str | None = url

        while next_url:
            data, next_url = await self._async_get_page(next_url)
            results.extend(data)

        return results

    async def _async_get_page(
        self, url: str
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch a single page and return data with next page URL."""
        data, headers = await self._async_request_json("GET", url)

        # Parse Link header for pagination: <url>; rel="next"
        next_url = None
        for link in headers.get("Link", "").split(","):
            if 'rel="next"' in link:
                match = re.search(r"<([^>]+)>", link)
                if match:
                    next_url = match.group(1)
                    break

        return data, next_url

    async def _async_request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> tuple[Any, Mapping[str, str]]:
        """
        Make an API request and decode the JSON body.

        Sending the request and reading the body share one timeout, and every
        failure (network, HTTP status, non-JSON body) is raised as a
        NavirecApiClientError subclass so callers only need to handle those.
        """
        try:
            async with asyncio.timeout(API_REQUEST_TIMEOUT):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    **kwargs,
                )
                try:
                    self._verify_response_or_raise(response)
                except Exception:
                    response.release()
                    raise
                return await response.json(), response.headers

        except TimeoutError as exception:
            msg = f"Timeout error fetching information from {url}"
            raise NavirecApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror, ValueError) as exception:
            # ValueError covers json.JSONDecodeError for malformed bodies;
            # aiohttp.ContentTypeError (a ClientError) covers non-JSON bodies
            # such as HTML error pages from proxies.
            msg = f"Error fetching information from {url}: {exception}"
            raise NavirecApiClientCommunicationError(msg) from exception

    def _verify_response_or_raise(self, response: aiohttp.ClientResponse) -> None:
        """Verify that the response is valid."""
        if response.status in (401, 403):
            msg = "Invalid credentials"
            raise NavirecApiClientAuthenticationError(msg)
        if response.status == 429:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            msg = f"Rate limited. Retry after {retry_after} seconds"
            raise NavirecApiClientRateLimitError(msg, retry_after)
        response.raise_for_status()


class NavirecStreamClient:
    """Navirec streaming client for ndjson streams."""

    def __init__(
        self,
        api_url: str,
        api_token: str,
        session: aiohttp.ClientSession,
        account_id: str,
        last_updated_at: str | None = None,
    ) -> None:
        """Initialize the stream client."""
        self._api_url = api_url.rstrip("/")
        self._api_token = api_token
        self._session = session
        self._account_id = account_id
        self._response: aiohttp.ClientResponse | None = None
        self._connected = False
        self._last_updated_at: str | None = last_updated_at
        self._should_stop = False

    @property
    def _headers(self) -> dict[str, str]:
        """Get headers for stream requests."""
        return {
            "Authorization": f"Token {self._api_token}",
            "Accept": f"application/x-ndjson; version={API_VERSION}",
            "User-Agent": USER_AGENT,
        }

    @property
    def connected(self) -> bool:
        """Return whether the stream is connected."""
        return self._connected

    @property
    def last_updated_at(self) -> str | None:
        """Return the last updated_at value for resume."""
        return self._last_updated_at

    async def async_connect(self) -> None:
        """Connect to the vehicle states stream."""
        url = f"{self._api_url}/streams/vehicle_states/?account={self._account_id}"

        # Add updated_at__gt for resume if we have a previous last_updated_at
        if self._last_updated_at:
            url = f"{url}&updated_at__gt={self._last_updated_at}"

        LOGGER.debug("Connecting to stream: %s", url)

        try:
            # The stream is long-lived so there is no total timeout, but the
            # connection attempt and each read (heartbeats every 30s) are bounded.
            self._response = await self._session.get(
                url,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(
                    total=None,
                    sock_connect=STREAM_CONNECT_TIMEOUT,
                    sock_read=STREAM_READ_TIMEOUT,
                ),
            )

            if self._response.status in (401, 403):
                msg = "Authentication failed for stream"
                raise NavirecApiClientAuthenticationError(msg)

            if self._response.status == 429:
                retry_after = parse_retry_after(
                    self._response.headers.get("Retry-After")
                )
                msg = f"Rate limited. Retry after {retry_after} seconds"
                raise NavirecApiClientRateLimitError(msg, retry_after)

            self._response.raise_for_status()
            self._connected = True
            LOGGER.info("Connected to Navirec stream for account %s", self._account_id)

        except (aiohttp.ClientError, socket.gaierror, TimeoutError) as exception:
            msg = f"Error connecting to stream: {exception!r}"
            raise NavirecApiClientCommunicationError(msg) from exception

    async def async_disconnect(self) -> None:
        """Disconnect from the stream."""
        self._should_stop = True
        self._connected = False
        if self._response:
            self._response.close()
            self._response = None
        LOGGER.debug(
            "Disconnected from Navirec stream for account %s", self._account_id
        )

    async def async_iter_events(self) -> AsyncIterator[dict[str, Any]]:
        """Iterate over stream events."""
        if not self._response:
            msg = "Stream not connected"
            raise NavirecApiClientError(msg)

        try:
            async for line in self._response.content:
                if self._should_stop:
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    event = json.loads(line_str)
                except json.JSONDecodeError as e:
                    LOGGER.warning("Failed to parse stream event: %s - %s", line_str, e)
                    continue

                # Track updated_at for resume capability
                if event.get("event") == "vehicle_state":
                    data = event.get("data", {})
                    if "updated_at" in data:
                        self._last_updated_at = data["updated_at"]

                yield event

        except aiohttp.ClientError as exception:
            self._connected = False
            LOGGER.warning("Stream connection lost: %r", exception)
            raise NavirecApiClientCommunicationError(
                f"Stream connection lost: {exception!r}"
            ) from exception
        finally:
            self._connected = False


class ReconnectBackoff:
    """
    Exponential reconnect backoff.

    Kept separate from NavirecStreamClient because a new stream client is
    created for every connection attempt, while the backoff has to grow
    across consecutive failed attempts.
    """

    def __init__(
        self,
        min_delay: float = STREAM_RECONNECT_MIN_DELAY,
        max_delay: float = STREAM_RECONNECT_MAX_DELAY,
        multiplier: float = STREAM_RECONNECT_MULTIPLIER,
    ) -> None:
        """Initialize the backoff."""
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._multiplier = multiplier
        self._delay = min_delay

    def next_delay(self) -> float:
        """Return the current delay and increase it for next time."""
        delay = self._delay
        self._delay = min(self._delay * self._multiplier, self._max_delay)
        return delay

    def reset(self) -> None:
        """Reset the delay after a healthy connection."""
        self._delay = self._min_delay
