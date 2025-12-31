"""Tests for Navirec config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navirec.const import (
    CONF_ACCOUNT_ID,
    CONF_API_TOKEN,
    CONF_API_URL,
    DOMAIN,
)


@pytest.fixture
def mock_accounts() -> list[dict[str, Any]]:
    """Return mock accounts data."""
    return [{"id": "test-account-id", "name": "Test Account"}]


@pytest.mark.asyncio
async def test_form_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_accounts: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch("custom_components.navirec.config_flow.NavirecApiClient") as mock_client:
        mock_client_instance = mock_client.return_value
        mock_client_instance.async_get_accounts = AsyncMock(return_value=mock_accounts)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: "https://api.navirec.com/",
                CONF_API_TOKEN: "test-token",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Account"
    assert result["data"] == {
        CONF_API_URL: "https://api.navirec.com",
        CONF_API_TOKEN: "test-token",
        CONF_ACCOUNT_ID: "test-account-id",
    }


@pytest.mark.asyncio
async def test_form_auth_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    enable_custom_integrations: None,
) -> None:
    """Test config flow with authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("custom_components.navirec.config_flow.NavirecApiClient") as mock_client:
        from custom_components.navirec.api import NavirecApiClientAuthenticationError

        mock_client_instance = mock_client.return_value
        mock_client_instance.async_get_accounts = AsyncMock(
            side_effect=NavirecApiClientAuthenticationError("Invalid credentials")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: "https://api.navirec.com/",
                CONF_API_TOKEN: "bad-token",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}


@pytest.mark.asyncio
async def test_form_connection_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    enable_custom_integrations: None,
) -> None:
    """Test config flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("custom_components.navirec.config_flow.NavirecApiClient") as mock_client:
        from custom_components.navirec.api import NavirecApiClientCommunicationError

        mock_client_instance = mock_client.return_value
        mock_client_instance.async_get_accounts = AsyncMock(
            side_effect=NavirecApiClientCommunicationError("Connection failed")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: "https://api.navirec.invalid/",
                CONF_API_TOKEN: "test-token",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "connection"}


@pytest.mark.asyncio
async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_accounts: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test config flow when already configured."""
    # Create an existing entry - unique_id is just the account_id
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Account",
        data={
            CONF_API_URL: "https://api.navirec.com",
            CONF_API_TOKEN: "existing-token",
            CONF_ACCOUNT_ID: "test-account-id",
        },
        unique_id="test-account-id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("custom_components.navirec.config_flow.NavirecApiClient") as mock_client:
        mock_client_instance = mock_client.return_value
        mock_client_instance.async_get_accounts = AsyncMock(return_value=mock_accounts)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: "https://api.navirec.com/",
                CONF_API_TOKEN: "test-token",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_form_with_account_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_accounts: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test successful config flow with explicit account_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch("custom_components.navirec.config_flow.NavirecApiClient") as mock_client:
        mock_client_instance = mock_client.return_value
        mock_client_instance.async_get_accounts = AsyncMock(return_value=mock_accounts)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: "https://api.navirec.com/",
                CONF_API_TOKEN: "test-token",
                CONF_ACCOUNT_ID: "test-account-id",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Account"
    assert result["data"][CONF_ACCOUNT_ID] == "test-account-id"


@pytest.mark.asyncio
async def test_form_invalid_account_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_accounts: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test config flow with invalid account_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("custom_components.navirec.config_flow.NavirecApiClient") as mock_client:
        mock_client_instance = mock_client.return_value
        mock_client_instance.async_get_accounts = AsyncMock(return_value=mock_accounts)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: "https://api.navirec.com/",
                CONF_API_TOKEN: "test-token",
                CONF_ACCOUNT_ID: "nonexistent-account-id",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}
