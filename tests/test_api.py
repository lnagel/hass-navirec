"""Tests for Navirec API client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.navirec.api import (
    NavirecApiClient,
    NavirecApiClientAuthenticationError,
    NavirecApiClientCommunicationError,
    NavirecApiClientError,
    NavirecApiClientRateLimitError,
    NavirecStreamClient,
)


def create_mock_response(
    status: int = 200,
    json_data: Any = None,
    headers: dict[str, str] | None = None,
) -> AsyncMock:
    """Create a mock aiohttp response with proper async methods."""
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = status
    mock_response.headers = headers or {}
    mock_response.json = AsyncMock(return_value=json_data or [])
    mock_response.raise_for_status = MagicMock()
    return mock_response


class TestNavirecApiClient:
    """Test NavirecApiClient."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock aiohttp session."""
        return MagicMock(spec=aiohttp.ClientSession)

    @pytest.fixture
    def api_client(self, mock_session: MagicMock) -> NavirecApiClient:
        """Create an API client instance."""
        return NavirecApiClient(
            api_url="https://api.navirec.test/",
            api_token="test-token",
            session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_get_accounts_success(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
        accounts_fixture: list[dict[str, Any]],
    ) -> None:
        """Test successful accounts fetch."""
        mock_response = create_mock_response(
            status=200,
            json_data=accounts_fixture,
            headers={},  # No Link header = no pagination
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        accounts = await api_client.async_get_accounts()
        assert len(accounts) == len(accounts_fixture)
        assert accounts[0]["id"] == accounts_fixture[0]["id"]

    @pytest.mark.asyncio
    async def test_get_accounts_auth_error(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
    ) -> None:
        """Test authentication error on accounts fetch."""
        mock_response = create_mock_response(status=401)
        mock_session.request = AsyncMock(return_value=mock_response)

        with pytest.raises(NavirecApiClientAuthenticationError):
            await api_client.async_get_accounts()

    @pytest.mark.asyncio
    async def test_get_accounts_rate_limit(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
    ) -> None:
        """Test rate limit error on accounts fetch."""
        mock_response = create_mock_response(
            status=429,
            headers={"Retry-After": "30"},
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        with pytest.raises(NavirecApiClientRateLimitError) as exc_info:
            await api_client.async_get_accounts()
        assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    async def test_validate_token_success(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
        accounts_fixture: list[dict[str, Any]],
    ) -> None:
        """Test successful token validation."""
        mock_response = create_mock_response(
            status=200,
            json_data=accounts_fixture,
            headers={},
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await api_client.async_validate_token()
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_token_invalid(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
    ) -> None:
        """Test invalid token validation."""
        mock_response = create_mock_response(status=401)
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await api_client.async_validate_token()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_vehicles_with_filter(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
    ) -> None:
        """Test vehicles fetch with account filter."""
        mock_response = create_mock_response(
            status=200,
            json_data=vehicles_fixture,
            headers={},
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        vehicles = await api_client.async_get_vehicles(
            account_id="test-account-id", active_only=True
        )
        assert len(vehicles) == len(vehicles_fixture)

        # Verify the URL included the filters
        call_args = mock_session.request.call_args
        assert "account=test-account-id" in call_args.kwargs["url"]
        assert "active=true" in call_args.kwargs["url"]

    @pytest.mark.asyncio
    async def test_get_vehicles_with_pagination(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
    ) -> None:
        """Test vehicles fetch with pagination via Link header."""
        # Split vehicles into two pages
        page1 = vehicles_fixture[:2]
        page2 = vehicles_fixture[2:]

        mock_response_page1 = create_mock_response(
            status=200,
            json_data=page1,
            headers={
                "Link": '<https://api.navirec.test/vehicles/?cursor=abc123>; rel="next"'
            },
        )
        mock_response_page2 = create_mock_response(
            status=200,
            json_data=page2,
            headers={},  # No next link = last page
        )

        mock_session.request = AsyncMock(
            side_effect=[mock_response_page1, mock_response_page2]
        )

        vehicles = await api_client.async_get_vehicles()

        # Should have all vehicles from both pages
        assert len(vehicles) == len(vehicles_fixture)
        # Should have made 2 requests
        assert mock_session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_sensors_with_pagination(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
        sensors_fixture: list[dict[str, Any]],
    ) -> None:
        """Test sensors fetch with pagination via Link header."""
        # Split sensors into two pages
        page1 = sensors_fixture[:5]
        page2 = sensors_fixture[5:10]
        page3 = sensors_fixture[10:]

        mock_response_page1 = create_mock_response(
            status=200,
            json_data=page1,
            headers={
                "Link": '<https://api.navirec.test/sensors/?cursor=abc123>; rel="next"'
            },
        )
        mock_response_page2 = create_mock_response(
            status=200,
            json_data=page2,
            headers={
                "Link": '<https://api.navirec.test/sensors/?cursor=def456>; rel="next", <https://api.navirec.test/sensors/>; rel="prev"'
            },
        )
        mock_response_page3 = create_mock_response(
            status=200,
            json_data=page3,
            headers={
                "Link": '<https://api.navirec.test/sensors/?cursor=abc123>; rel="prev"'
            },  # Only prev link = last page
        )

        mock_session.request = AsyncMock(
            side_effect=[mock_response_page1, mock_response_page2, mock_response_page3]
        )

        sensors = await api_client.async_get_sensors(account_id="test-account-id")

        # Should have all sensors from all pages
        assert len(sensors) == len(sensors_fixture)
        # Should have made 3 requests
        assert mock_session.request.call_count == 3

    @pytest.mark.asyncio
    async def test_get_accounts_no_pagination(
        self,
        api_client: NavirecApiClient,
        mock_session: MagicMock,
        accounts_fixture: list[dict[str, Any]],
    ) -> None:
        """Test that accounts fetch does NOT follow pagination."""
        # Even if server returns Link header, accounts should only fetch first page
        mock_response = create_mock_response(
            status=200,
            json_data=accounts_fixture,
            headers={
                "Link": '<https://api.navirec.test/accounts/?cursor=abc123>; rel="next"'
            },
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        accounts = await api_client.async_get_accounts()

        # Should only return first page data
        assert len(accounts) == len(accounts_fixture)
        # Should have made only 1 request (no pagination follow)
        assert mock_session.request.call_count == 1


class TestNavirecStreamClient:
    """Test NavirecStreamClient."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock aiohttp session."""
        return MagicMock(spec=aiohttp.ClientSession)

    @pytest.fixture
    def stream_client(self, mock_session: MagicMock) -> NavirecStreamClient:
        """Create a stream client instance."""
        return NavirecStreamClient(
            api_url="https://api.navirec.test/",
            api_token="test-token",
            session=mock_session,
            account_id="test-account-id",
        )

    def test_reconnect_delay_exponential_backoff(
        self, stream_client: NavirecStreamClient
    ) -> None:
        """Test reconnect delay increases exponentially."""
        delay1 = stream_client.get_reconnect_delay()
        assert delay1 == 1  # Initial delay

        delay2 = stream_client.get_reconnect_delay()
        assert delay2 == 2

        delay3 = stream_client.get_reconnect_delay()
        assert delay3 == 4

        delay4 = stream_client.get_reconnect_delay()
        assert delay4 == 8

    def test_reconnect_delay_max_cap(self, stream_client: NavirecStreamClient) -> None:
        """Test reconnect delay is capped at maximum."""
        # Get delays until we hit the cap
        for _ in range(10):
            stream_client.get_reconnect_delay()

        delay = stream_client.get_reconnect_delay()
        assert delay == 60  # Max delay

    def test_reset_reconnect_delay(self, stream_client: NavirecStreamClient) -> None:
        """Test resetting reconnect delay."""
        # Increase delay
        stream_client.get_reconnect_delay()
        stream_client.get_reconnect_delay()

        # Reset
        stream_client.reset_reconnect_delay()

        # Should be back to initial
        delay = stream_client.get_reconnect_delay()
        assert delay == 1

    def test_initial_last_updated_at_none(self, mock_session: MagicMock) -> None:
        """Test stream client initializes with no last_updated_at by default."""
        client = NavirecStreamClient(
            api_url="https://api.navirec.test/",
            api_token="test-token",
            session=mock_session,
            account_id="test-account-id",
        )

        assert client.last_updated_at is None

    def test_initial_last_updated_at_provided(self, mock_session: MagicMock) -> None:
        """Test stream client initializes with provided last_updated_at."""
        last_updated_at = "2025-12-31T19:09:24.796730Z"
        client = NavirecStreamClient(
            api_url="https://api.navirec.test/",
            api_token="test-token",
            session=mock_session,
            account_id="test-account-id",
            last_updated_at=last_updated_at,
        )

        assert client.last_updated_at == last_updated_at

    @pytest.mark.asyncio
    async def test_connect_without_last_updated_at(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test connection URL without last_updated_at parameter."""
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_session.get = AsyncMock(return_value=mock_response)

        await stream_client.async_connect()

        # Verify URL doesn't include updated_at__gt parameter
        call_args = mock_session.get.call_args
        url = call_args.args[0]
        assert "updated_at__gt" not in url
        assert url.endswith("?account=test-account-id")

    @pytest.mark.asyncio
    async def test_connect_with_last_updated_at(self, mock_session: MagicMock) -> None:
        """Test connection URL includes last_updated_at parameter when provided."""
        last_updated_at = "2025-12-31T19:09:24.796730Z"
        client = NavirecStreamClient(
            api_url="https://api.navirec.test/",
            api_token="test-token",
            session=mock_session,
            account_id="test-account-id",
            last_updated_at=last_updated_at,
        )

        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_session.get = AsyncMock(return_value=mock_response)

        await client.async_connect()

        # Verify URL includes updated_at__gt parameter
        call_args = mock_session.get.call_args
        url = call_args.args[0]
        assert "updated_at__gt=" in url
        assert last_updated_at in url
        assert "account=test-account-id" in url

    @pytest.mark.asyncio
    async def test_connect_auth_error(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test authentication error during connect."""
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 401
        mock_response.headers = {}
        mock_session.get = AsyncMock(return_value=mock_response)

        with pytest.raises(NavirecApiClientAuthenticationError):
            await stream_client.async_connect()

        assert stream_client.connected is False

    @pytest.mark.asyncio
    async def test_connect_rate_limit(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test rate limit error during connect."""
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "45"}
        mock_session.get = AsyncMock(return_value=mock_response)

        with pytest.raises(NavirecApiClientRateLimitError) as exc_info:
            await stream_client.async_connect()

        assert exc_info.value.retry_after == 45
        assert stream_client.connected is False

    @pytest.mark.asyncio
    async def test_connect_communication_error(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test communication error during connect."""
        mock_session.get = AsyncMock(side_effect=aiohttp.ClientError("Network error"))

        with pytest.raises(NavirecApiClientCommunicationError):
            await stream_client.async_connect()

        assert stream_client.connected is False

    @pytest.mark.asyncio
    async def test_disconnect(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test disconnect clears state."""
        # First connect successfully
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.close = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_response)

        await stream_client.async_connect()
        assert stream_client.connected is True

        # Now disconnect
        await stream_client.async_disconnect()

        assert stream_client.connected is False
        mock_response.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_iter_events_not_connected(
        self, stream_client: NavirecStreamClient
    ) -> None:
        """Test iter_events raises when not connected."""
        with pytest.raises(NavirecApiClientError) as exc_info:
            async for _ in stream_client.async_iter_events():
                pass  # pragma: no cover

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_iter_events_success(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test successful event iteration."""
        # Create mock response with async iterator content
        events = [
            b'{"event": "connected"}\n',
            b'{"event": "vehicle_state", "data": {"vehicle": "https://api/vehicles/123/", "updated_at": "2025-01-01T00:00:00Z"}}\n',
            b'{"event": "heartbeat"}\n',
        ]

        async def mock_content_iterator():
            for event in events:
                yield event

        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.content = mock_content_iterator()
        mock_session.get = AsyncMock(return_value=mock_response)

        await stream_client.async_connect()

        received_events = [event async for event in stream_client.async_iter_events()]

        assert len(received_events) == 3
        assert received_events[0]["event"] == "connected"
        assert received_events[1]["event"] == "vehicle_state"
        assert received_events[2]["event"] == "heartbeat"

        # Verify last_updated_at was tracked
        assert stream_client.last_updated_at == "2025-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_iter_events_json_decode_error(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test handling of malformed JSON in stream."""
        # Include malformed JSON that should be skipped
        events = [
            b'{"event": "connected"}\n',
            b"not valid json\n",
            b'{"event": "heartbeat"}\n',
        ]

        async def mock_content_iterator():
            for event in events:
                yield event

        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.content = mock_content_iterator()
        mock_session.get = AsyncMock(return_value=mock_response)

        await stream_client.async_connect()

        received_events = [event async for event in stream_client.async_iter_events()]

        # Should only have 2 valid events (malformed JSON skipped)
        assert len(received_events) == 2
        assert received_events[0]["event"] == "connected"
        assert received_events[1]["event"] == "heartbeat"

    @pytest.mark.asyncio
    async def test_iter_events_empty_lines_skipped(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test that empty lines are skipped."""
        events = [
            b'{"event": "connected"}\n',
            b"\n",
            b"   \n",
            b'{"event": "heartbeat"}\n',
        ]

        async def mock_content_iterator():
            for event in events:
                yield event

        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.content = mock_content_iterator()
        mock_session.get = AsyncMock(return_value=mock_response)

        await stream_client.async_connect()

        received_events = [event async for event in stream_client.async_iter_events()]

        assert len(received_events) == 2

    @pytest.mark.asyncio
    async def test_iter_events_connection_lost(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test handling of connection loss during iteration."""

        async def mock_content_iterator():
            yield b'{"event": "connected"}\n'
            raise aiohttp.ClientError("Connection lost")

        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.content = mock_content_iterator()
        mock_session.get = AsyncMock(return_value=mock_response)

        await stream_client.async_connect()

        async def collect_events():
            return [event async for event in stream_client.async_iter_events()]

        with pytest.raises(NavirecApiClientCommunicationError):
            await collect_events()

        # connected should be False after connection loss
        assert stream_client.connected is False

    @pytest.mark.asyncio
    async def test_iter_events_stops_when_should_stop(
        self, stream_client: NavirecStreamClient, mock_session: MagicMock
    ) -> None:
        """Test that iteration stops when _should_stop is set."""

        async def mock_content_iterator():
            yield b'{"event": "connected"}\n'
            # Set should_stop before yielding more events
            stream_client._should_stop = True
            yield b'{"event": "heartbeat"}\n'

        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.content = mock_content_iterator()
        mock_session.get = AsyncMock(return_value=mock_response)

        await stream_client.async_connect()

        received_events = [event async for event in stream_client.async_iter_events()]

        # Should only have received first event before stop
        assert len(received_events) == 1
