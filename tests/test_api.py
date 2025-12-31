"""Tests for Navirec API client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.navirec.api import (
    NavirecApiClient,
    NavirecApiClientAuthenticationError,
    NavirecApiClientRateLimitError,
    NavirecStreamClient,
    _extract_uuid_from_url,
)


class TestExtractUuidFromUrl:
    """Test UUID extraction from URLs."""

    def test_extract_uuid_from_vehicle_url(self) -> None:
        """Test extracting UUID from a vehicle URL."""
        url = "https://api.navirec.com/vehicles/924da156-1a68-4fce-8da1-a196c9bf22be/"
        assert _extract_uuid_from_url(url) == "924da156-1a68-4fce-8da1-a196c9bf22be"

    def test_extract_uuid_from_account_url(self) -> None:
        """Test extracting UUID from an account URL."""
        url = "https://api.navirec.com/accounts/89ea89c8-bffb-444a-9876-c54a865e4d67/"
        assert _extract_uuid_from_url(url) == "89ea89c8-bffb-444a-9876-c54a865e4d67"

    def test_extract_uuid_invalid_url(self) -> None:
        """Test extracting UUID from invalid URL raises ValueError."""
        with pytest.raises(ValueError, match="Could not extract UUID"):
            _extract_uuid_from_url("https://api.navirec.com/invalid/")


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
