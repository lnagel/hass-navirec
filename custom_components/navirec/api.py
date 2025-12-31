"""Navirec API Client."""

from __future__ import annotations

import asyncio
import json
import re
import socket
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import (
    API_VERSION,
    LOGGER,
    STREAM_RECONNECT_MAX_DELAY,
    STREAM_RECONNECT_MIN_DELAY,
    STREAM_RECONNECT_MULTIPLIER,
    USER_AGENT,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class NavirecApiClientError(Exception):
    """Exception to indicate a general API error."""


class NavirecApiClientCommunicationError(NavirecApiClientError):
    """Exception to indicate a communication error."""


class NavirecApiClientAuthenticationError(NavirecApiClientError):
    """Exception to indicate an authentication error."""


class NavirecApiClientRateLimitError(NavirecApiClientError):
    """Exception to indicate rate limiting."""

    def __init__(self, message: str, retry_after: int = 60) -> None:
        """Initialize rate limit error."""
        super().__init__(message)
        self.retry_after = retry_after


def _extract_uuid_from_url(url: str) -> str:
    """Extract UUID from a Navirec API URL."""
    # URL format: https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/
    match = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", url
    )
    if match:
        return match.group(0)
    msg = f"Could not extract UUID from URL: {url}"
    raise ValueError(msg)


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
        """Get all accounts accessible by the token."""
        return await self._async_get_paginated(f"{self._api_url}/accounts/")

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
        response = await self._async_request("GET", url)

        # Parse Link header for pagination
        next_url = None
        if isinstance(response, aiohttp.ClientResponse):
            link_header = response.headers.get("Link", "")
            # Parse: <url>; rel="next"
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    match = re.search(r"<([^>]+)>", link)
                    if match:
                        next_url = match.group(1)
                        break

            data = await response.json()
            return data, next_url

        # Response is already parsed JSON (from _async_request wrapper)
        return response, None

    async def _async_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Make an API request."""
        try:
            async with asyncio.timeout(30):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    **kwargs,
                )
                self._verify_response_or_raise(response)
                return response

        except TimeoutError as exception:
            msg = f"Timeout error fetching information from {url}"
            raise NavirecApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information from {url}: {exception}"
            raise NavirecApiClientCommunicationError(msg) from exception

    def _verify_response_or_raise(self, response: aiohttp.ClientResponse) -> None:
        """Verify that the response is valid."""
        if response.status in (401, 403):
            msg = "Invalid credentials"
            raise NavirecApiClientAuthenticationError(msg)
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
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
    ) -> None:
        """Initialize the stream client."""
        self._api_url = api_url.rstrip("/")
        self._api_token = api_token
        self._session = session
        self._account_id = account_id
        self._response: aiohttp.ClientResponse | None = None
        self._connected = False
        self._last_updated_at: str | None = None
        self._reconnect_delay = STREAM_RECONNECT_MIN_DELAY
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
        """Return the last updated_at timestamp for resume."""
        return self._last_updated_at

    async def async_connect(self) -> None:
        """Connect to the vehicle states stream."""
        url = f"{self._api_url}/streams/vehicle_states/?account={self._account_id}"

        # Add updated_at__gt for resume if we have a previous timestamp
        if self._last_updated_at:
            url = f"{url}&updated_at__gt={self._last_updated_at}"

        LOGGER.debug("Connecting to stream: %s", url)

        try:
            self._response = await self._session.get(
                url,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=None, sock_read=90),
            )

            if self._response.status in (401, 403):
                msg = "Authentication failed for stream"
                raise NavirecApiClientAuthenticationError(msg)

            if self._response.status == 429:
                retry_after = int(self._response.headers.get("Retry-After", "60"))
                msg = f"Rate limited. Retry after {retry_after} seconds"
                raise NavirecApiClientRateLimitError(msg, retry_after)

            self._response.raise_for_status()
            self._connected = True
            self._reconnect_delay = STREAM_RECONNECT_MIN_DELAY
            LOGGER.info("Connected to Navirec stream for account %s", self._account_id)

        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error connecting to stream: {exception}"
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

        except (aiohttp.ClientError, asyncio.CancelledError) as exception:
            self._connected = False
            LOGGER.warning("Stream connection lost: %s", exception)
            raise NavirecApiClientCommunicationError(
                f"Stream connection lost: {exception}"
            ) from exception
        finally:
            self._connected = False

    def get_reconnect_delay(self) -> float:
        """Get the current reconnect delay and increase it for next time."""
        delay = self._reconnect_delay
        self._reconnect_delay = min(
            self._reconnect_delay * STREAM_RECONNECT_MULTIPLIER,
            STREAM_RECONNECT_MAX_DELAY,
        )
        return delay

    def reset_reconnect_delay(self) -> None:
        """Reset reconnect delay after successful connection."""
        self._reconnect_delay = STREAM_RECONNECT_MIN_DELAY
